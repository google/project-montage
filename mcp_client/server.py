# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Landing page + ADK chat web interface for Project Montage."""

from __future__ import annotations

import mimetypes
import tomllib
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import google.auth
import google.auth.transport.requests
import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli import fast_api as adk_fast_api
from google.adk.cli.service_registry import get_service_registry
from google.adk.errors.already_exists_error import AlreadyExistsError
from google.adk.sessions.base_session_service import BaseSessionService
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.oauth2 import id_token
from pydantic import BaseModel, Field
from shared.constants import SERVER_URL, SESSION_SERVICE_URI
from starlette.concurrency import run_in_threadpool
from utils.fork_link import FORK_LINK_PATH
from utils.forking import EventNotFoundError, SessionNotFoundError, perform_fork
from utils.iap_identity import parse_iap_identity

# Cloud Run's built-in IAP integration forwards this header once a request
# is authenticated; it's absent for local/non-IAP deployments.
_IAP_USER_EMAIL_HEADER = "x-goog-authenticated-user-email"

mimetypes.add_type("text/javascript", ".js")

# When SESSION_SERVICE_URI is unset, ADK's own "no URI" fallback (per-agent
# local SQLite if writable, else in-memory) constructs its session service
# independently of ours, so our own routes and ADK's dev-ui/session routes
# would silently operate on two disconnected stores. Registering a custom
# scheme lets us hand ADK the exact same InMemorySessionService instance we
# use ourselves -- see create_app().
_SHARED_MEMORY_SESSION_SERVICE_URI = "mcp-client-memory://shared"


def _read_index_html() -> str:
  index_path = Path(__file__).resolve().parent / "frontend" / "index.html"
  if index_path.exists():
    return index_path.read_text(encoding="utf-8")
  return "<!doctype html><html><body><h1>Project Montage</h1></body></html>"


def _inject_default_user_id(html: str, *, display_name: str | None) -> str:
  # display_name is derived from an attacker-controllable request header
  # (X-Goog-Authenticated-User-Email); it's spliced into a quoted HTML
  # attribute below, so it must be escaped even though IAP itself only
  # ever forwards real Google account emails.
  safe_display_name = escape(display_name or "", quote=True)
  return html.replace("__DEFAULT_USER_ID__", safe_display_name)


def _read_project_version() -> str:
  pyproject_path = Path(__file__).resolve().parents[0] / "pyproject.toml"
  try:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
  except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
    return "unknown"
  return str(data.get("project", {}).get("version", "unknown"))


def _get_versions() -> dict[str, str]:
  web_version = _read_project_version()
  mcp_version = _fetch_mcp_version()
  return {"web_version": web_version, "mcp_version": mcp_version}


def _get_auth_headers(url: str) -> dict[str, str]:
  if "localhost" in url or "127.0.0.1" in url:
    return {}
  try:
    auth_req = google.auth.transport.requests.Request()
    if "https" in url:
      token = id_token.fetch_id_token(auth_req, url)
      return {"Authorization": f"Bearer {token}"}
    return {}
  except Exception:
    return {}


def _fetch_mcp_version() -> str:
  url = f"{SERVER_URL}/version"
  headers = _get_auth_headers(url)
  try:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
  except Exception:
    return "unknown"
  try:
    data = response.json()
  except ValueError:
    return "unknown"
  return str(data.get("version", "unknown"))


class CreateADKSessionRequest(BaseModel):
  user_id: str = Field(..., min_length=1)
  app_name: str = "project_montage"
  session_id: str | None = None


class ForkSessionRequest(BaseModel):
  up_to_event_id: str = Field(..., min_length=1)


def create_app(*, agents_dir: str = "adk") -> FastAPI:
  db_session_service: DatabaseSessionService | None = None
  memory_session_service: InMemorySessionService | None = None
  effective_session_service_uri = SESSION_SERVICE_URI

  if not SESSION_SERVICE_URI:
    memory_session_service = InMemorySessionService()
    get_service_registry().register_session_service(
      "mcp-client-memory", lambda uri, **kwargs: memory_session_service
    )
    effective_session_service_uri = _SHARED_MEMORY_SESSION_SERVICE_URI

  @asynccontextmanager
  async def lifespan(app: FastAPI):
    try:
      yield
    finally:
      if db_session_service is not None:
        await db_session_service.close()

  app = adk_fast_api.get_fast_api_app(
    agents_dir=agents_dir,
    web=True,
    session_service_uri=effective_session_service_uri,
    lifespan=lifespan,
  )

  # Mount static files for frontend assets
  frontend_path = Path(__file__).resolve().parent / "frontend"
  app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

  # Remove ADK's default root redirect so we can own "/".
  app.router.routes = [
    route for route in app.router.routes if getattr(route, "path", None) != "/"
  ]  # noqa: E501

  def _get_session_service() -> BaseSessionService:
    nonlocal db_session_service
    if memory_session_service is not None:
      return memory_session_service
    if db_session_service is None:
      db_session_service = DatabaseSessionService(db_url=SESSION_SERVICE_URI)
    return db_session_service

  @app.get("/", response_class=HTMLResponse)
  async def landing_page(request: Request) -> str:
    identity = parse_iap_identity(request.headers.get(_IAP_USER_EMAIL_HEADER))
    return _inject_default_user_id(
      _read_index_html(), display_name=identity.display_name
    )

  @app.get("/versions")
  async def versions() -> dict[str, str]:
    return await run_in_threadpool(_get_versions)

  @app.post("/sessions")
  async def create_session(req: CreateADKSessionRequest) -> dict[str, str]:
    if not SESSION_SERVICE_URI:
      return {
        "id": "",
        "app_name": req.app_name,
        "user_id": req.user_id,
        "bypass": "true",
      }
    try:
      session = await _get_session_service().create_session(
        app_name=req.app_name,
        user_id=req.user_id,
        session_id=req.session_id,
      )
    except AlreadyExistsError as exc:
      raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
      "id": session.id,
      "app_name": session.app_name,
      "user_id": session.user_id,
      "bypass": "false",
    }

  @app.post("/sessions/{app_name}/{user_id}/{session_id}/fork")
  async def fork_session(
    app_name: str, user_id: str, session_id: str, req: ForkSessionRequest
  ) -> dict[str, str]:
    service = _get_session_service()
    try:
      new_session_id = await perform_fork(
        service,
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        up_to_event_id=req.up_to_event_id,
      )
    except SessionNotFoundError as exc:
      raise HTTPException(status_code=404, detail="Session not found") from exc
    except EventNotFoundError as exc:
      raise HTTPException(
        status_code=404, detail="Event not found in session"
      ) from exc
    return {"new_session_id": new_session_id}

  @app.get(FORK_LINK_PATH)
  async def fork_session_via_link(
    app_name: str = Query(alias="app"),
    user_id: str = Query(alias="user"),
    session_id: str = Query(alias="session"),
    event_id: str = Query(alias="event"),
  ) -> RedirectResponse:
    """GET-triggered fork, for the in-chat link emitted by
    after_agent_callback. A markdown link in the vendored dev-ui can only
    issue a GET, so it cannot reach the POST route above. Forking is purely
    additive -- it never mutates the source -- so a GET that mutates is an
    accepted tradeoff here (see the spec's "New route" section).
    """
    service = _get_session_service()
    try:
      new_session_id = await perform_fork(
        service,
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        up_to_event_id=event_id,
      )
    except SessionNotFoundError as exc:
      raise HTTPException(status_code=404, detail="Session not found") from exc
    except EventNotFoundError as exc:
      raise HTTPException(
        status_code=404, detail="Event not found in session"
      ) from exc
    query = urlencode(
      {"app": app_name, "session": new_session_id, "userId": user_id}
    )
    return RedirectResponse(url=f"/dev-ui/?{query}", status_code=303)

  return app


# Uvicorn entrypoint:
#   uvicorn mcp_client.server:app --reload --host 127.0.0.1 --port 8000
app = create_app()
