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

"""Agent configuration for the MCP client."""

import logging
import os

import google.auth
import google.auth.transport.requests
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_session_manager import (
  SseConnectionParams,
  StdioConnectionParams,
  StreamableHTTPConnectionParams,
)
from google.adk.tools.mcp_tool.mcp_toolset import (
  MCPToolset,
)
from google.genai import types
from google.oauth2 import id_token
from mcp import StdioServerParameters
from shared.constants import SERVER_CONNECTION_TYPE, SERVER_URL
from utils.state import (
  after_tool_callback,
  before_agent_callback,
)

from .system_prompt import SYSTEM_INSTRUCTION


def get_auth_headers(url: str) -> dict[str, str]:
  """Get authorization headers for Cloud Run."""
  if "localhost" in url or "127.0.0.1" in url:
    return {}

  try:
    auth_req = google.auth.transport.requests.Request()
    if "https" in url:
      token = id_token.fetch_id_token(auth_req, url)
      return {"Authorization": f"Bearer {token}"}
    return {}
  except Exception as e:
    logging.error(f"Failed to get auth token: {e}")
    return {}


sse_server_params = SseConnectionParams(
  url=f"{SERVER_URL}/sse",
  headers=get_auth_headers(f"{SERVER_URL}/sse"),
  timeout=30,
  sse_read_timeout=800,
)

http_server_params = StreamableHTTPConnectionParams(
  url=f"{SERVER_URL}/mcp",
  headers=get_auth_headers(f"{SERVER_URL}/mcp"),
  timeout=30,
  sse_read_timeout=800,
)

stdio_server_params = StdioServerParameters(
  command="python",
  args=["./mcp_montage/server.py"],
  env=dict(os.environ),
)

# Select connection params based on config
server_type = SERVER_CONNECTION_TYPE.lower()
if server_type == "sse":
  connection_params = sse_server_params
elif server_type == "http":
  connection_params = http_server_params
else:
  connection_params = StdioConnectionParams(
    server_params=stdio_server_params,
    timeout=800,
  )

root_agent = LlmAgent(
  model="gemini-3.1-flash-lite",
  name="OrchestratorAgent",
  instruction=SYSTEM_INSTRUCTION,
  tools=[
    MCPToolset(
      connection_params=connection_params,
      header_provider=lambda ctx: get_auth_headers(f"{SERVER_URL}/mcp"),
      tool_filter=[
        "select_asset",
        "generate_storyboard_by_text",
        "generate_storyboard_by_image",
        "generate_images",
        "resize_image",
        "generate_videos",
        "concatenate_videos",
        "generate_bgm_and_merge",
        "generate_scene_narratives",
      ],
    )
  ],
  generate_content_config=types.GenerateContentConfig(
    temperature=0,
    tool_config=types.ToolConfig(
      function_calling_config=types.FunctionCallingConfig(
        mode=types.FunctionCallingConfigMode.VALIDATED,
      )
    ),
  ),
  before_agent_callback=before_agent_callback,
  after_tool_callback=after_tool_callback,
)
