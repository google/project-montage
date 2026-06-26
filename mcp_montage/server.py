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

import os

from services.speech_service import warm_up_forced_alignment_model
from shared.constants import GCS_BUCKET_NAME
from tools import register_all_tools
from utils import MCPServer, MCPServerConfig

_server_name = "MediaProductionServer"

_server_instructions = """\
A Media Production server designed to provide advanced image and video generation capabilities using Google's latest GenAI models for text, image, video, and music generation. \
It enables users to create video stories from text and image inputs.
"""  # noqa: E501

# Warm up the forced-alignment model at boot so the ~1.2 GB load doesn't spike
# memory mid-request (the OOM seen on small Cloud Run instances). Set
# WARM_UP_FORCED_ALIGNMENT=false to skip it locally and keep startup light.
_warm_up_enabled = os.getenv(
  "WARM_UP_FORCED_ALIGNMENT", "true"
).strip().lower() not in {"false", "0", "no"}
_startup_hooks = [warm_up_forced_alignment_model] if _warm_up_enabled else []

server = MCPServer(
  MCPServerConfig(
    name=_server_name,
    instructions=_server_instructions,
  ),
  on_startup=_startup_hooks,
)
mcp = server.mcp
app = server.app
logger = server.logger
bucket_name = GCS_BUCKET_NAME

register_all_tools(mcp, logger, bucket_name)

if __name__ == "__main__":
  server.run_stdio()
