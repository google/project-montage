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

"""The MCP server entry point.

Usage:
```
uvicorn mcp_montage.server:app --port 8001 --reload
```
"""

from schemas import MCPServerConfig
from shared.constants import GCS_BUCKET_NAME
from tools import register_all_tools
from utils import MCPServer

_server_name = "MediaProductionServer"

_server_instructions = """\
A Media Production server designed to provide advanced image and video generation capabilities using Google's latest GenAI models for text, image, video, and music generation. \
It enables users to create video stories from text and image inputs.
"""  # noqa: E501

server = MCPServer(
  MCPServerConfig(
    name=_server_name,
    instructions=_server_instructions,
  )
)
mcp = server.mcp
app = server.app
logger = server.logger
bucket_name = GCS_BUCKET_NAME

register_all_tools(mcp, logger, bucket_name)

if __name__ == "__main__":
  server.run_stdio()
