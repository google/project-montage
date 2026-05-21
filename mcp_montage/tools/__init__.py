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

"""Tool registration helpers."""

from __future__ import annotations

from collections.abc import Sequence
from logging import Logger
from typing import Protocol

from mcp.server.fastmcp import FastMCP


class ToolRegistrar(Protocol):
  def __call__(
    self, mcp: FastMCP, logger: Logger, bucket_name: str
  ) -> None: ...


def register_all_tools(mcp: FastMCP, logger: Logger, bucket_name: str) -> None:
  """Register every MCP tool with the provided FastMCP instance."""

  if not bucket_name:
    raise ValueError("GCS_BUCKET_NAME environment variable is not set.")

  for register in _REGISTRARS:
    register(mcp, logger, bucket_name)


from tools.asset_selector import register_asset_selector_tool
from tools.concatenate_videos import (
  register_concatenate_videos_tool,
)
from tools.generate_bgm_and_merge import (
  register_generate_bgm_and_merge_tool,
)
from tools.generate_image import register_generate_images_tool
from tools.generate_scene_narratives import (
  register_generate_scene_narratives_tool,
)
from tools.generate_storyboard import (
  register_generate_storyboard_tool,
)
from tools.generate_video import register_generate_video_tool

_REGISTRARS: Sequence[ToolRegistrar] = (
  register_generate_storyboard_tool,
  register_generate_images_tool,
  register_generate_video_tool,
  register_concatenate_videos_tool,
  register_generate_bgm_and_merge_tool,
  register_asset_selector_tool,
  register_generate_scene_narratives_tool,
)

__all__ = ["register_all_tools"]
