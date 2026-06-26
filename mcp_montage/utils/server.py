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

"""FastMCP + Starlette wiring utilities."""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from utils import log

__all__ = ["MCPServer", "MCPServerConfig"]


@dataclass(slots=True)
class MCPServerConfig:
  """Configuration for a FastMCP server instance."""

  name: str
  instructions: str = ""
  messages_mount: str = "/messages/"
  http_debug: bool = True


class MCPServer:
  """Helper that wires FastMCP with Starlette + SSE plumbing."""

  def __init__(
    self,
    config: MCPServerConfig,
    on_startup: Sequence[Callable[[], object]] | None = None,
  ) -> None:
    self.config = config
    self.logger = log.get_logger()
    self._on_startup: list[Callable[[], object]] = list(on_startup or [])
    self.mcp = FastMCP(
      name=config.name,
      instructions=config.instructions,
      transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
      ),
      stateless_http=True,
    )
    self._sse = SseServerTransport(config.messages_mount)
    self._http_app = self.mcp.streamable_http_app()
    self.app = Starlette(
      debug=config.http_debug,
      routes=[
        Route("/version", endpoint=self.handle_version),
        Route("/sse", endpoint=self.handle_sse),
        Mount(config.messages_mount, app=self._sse.handle_post_message),
        Mount("/", app=self._http_app),
      ],
      lifespan=self.lifespan,
    )

  @asynccontextmanager
  async def lifespan(self, app: Starlette):
    async with self._http_app.router.lifespan_context(app) as _:
      self._run_startup_hooks()
      yield

  def _run_startup_hooks(self) -> None:
    """Run each registered startup hook once, in registration order."""
    for hook in self._on_startup:
      hook()

  async def handle_sse(self, request: Request) -> Response:
    server = self.mcp._mcp_server
    async with self._sse.connect_sse(
      request.scope, request.receive, request._send
    ) as (
      reader,
      writer,
    ):
      await server.run(reader, writer, server.create_initialization_options())
    # Starlette expects an ASGI callable/Response; returning Response avoids NoneType errors. # noqa: E501
    return Response()

  async def handle_version(self, request: Request) -> Response:
    version = self._read_project_version()
    return JSONResponse({"version": version})

  def run_stdio(self) -> None:
    self.mcp.run(transport="stdio")

  def _read_project_version(self) -> str:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    try:
      data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
      return "unknown"
    return str(data.get("project", {}).get("version", "unknown"))
