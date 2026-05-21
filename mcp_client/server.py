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

import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli import fast_api as adk_fast_api
from google.adk.errors.already_exists_error import AlreadyExistsError
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.oauth2 import id_token
from pydantic import BaseModel, Field
from shared.constants import SERVER_URL, SESSION_SERVICE_URI
from starlette.concurrency import run_in_threadpool


def _read_index_html() -> str:
  index_path = Path(__file__).resolve().parent / "frontend" / "index.html"
  if index_path.exists():
    return index_path.read_text(encoding="utf-8")
  return "<!doctype html><html><body><h1>Project Montage</h1></body></html>"


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
    response = requests.get(url, headers=headers, timeout=5)
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


def create_app(*, agents_dir: str = "adk") -> FastAPI:
  db_session_service: DatabaseSessionService | None = None

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
    session_service_uri=SESSION_SERVICE_URI,
    lifespan=lifespan,
  )

  # Mount static files for frontend assets
  frontend_path = Path(__file__).resolve().parent / "frontend"
  app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

  # Remove ADK's default root redirect so we can own "/".
  app.router.routes = [
    route for route in app.router.routes if getattr(route, "path", None) != "/"
  ]  # noqa: E501

  def _get_db_session_service() -> DatabaseSessionService:
    nonlocal db_session_service
    if db_session_service is None:
      if not SESSION_SERVICE_URI:
        raise HTTPException(
          status_code=501,
          detail="SESSION_SERVICE_URI is not configured.",
        )
      db_session_service = DatabaseSessionService(db_url=SESSION_SERVICE_URI)
    return db_session_service

  @app.get("/", response_class=HTMLResponse)
  async def landing_page() -> str:
    return _read_index_html()

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
      session = await _get_db_session_service().create_session(
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

  return app


# Uvicorn entrypoint:
#   uvicorn mcp_client.server:app --reload --host 127.0.0.1 --port 8000
app = create_app()
