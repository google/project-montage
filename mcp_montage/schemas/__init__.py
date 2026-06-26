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

"""Schemas used by MCP servers.

Only shared output/value types live here. Per-tool request schemas live next
to the tool they belong to under `mcp_montage/tools/` so editing a tool's
input description doesn't require touching this package.
"""

from schemas.image import ImageMetadata
from schemas.storyboard import SceneImage, Storyboard, StoryboardScene
from schemas.video import (
  AudioMetadata,
  Narrative,
  NarrativeLine,
  VideoMetadata,
)
from schemas.voice import VoiceProfile

__all__ = [
  "ImageMetadata",
  "VideoMetadata",
  "AudioMetadata",
  "NarrativeLine",
  "Narrative",
  "Storyboard",
  "StoryboardScene",
  "SceneImage",
  "VoiceProfile",
]
