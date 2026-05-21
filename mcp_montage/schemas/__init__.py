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

"""Schemas used by MCP servers."""

from schemas.config import MCPServerConfig
from schemas.file import FileMetadata
from schemas.image import (
  ImageGenerationRequest,
  ImageMetadata,
  ResizeImageRequest,
  SelectAssetRequest,
)
from schemas.storyboard import StoryBoardGenerationRequest
from schemas.video import (
  ConcatenateVideosRequest,
  GenerateBGMAndMergeRequest,
  GenerateSceneNarrativesRequest,
  GenerateSceneNarrativesResponse,
  VideoGenerationRequest,
  VideoMetadata,
)

__all__ = [
  "MCPServerConfig",
  "VideoGenerationRequest",
  "ConcatenateVideosRequest",
  "GenerateBGMAndMergeRequest",
  "StoryBoardGenerationRequest",
  "ImageGenerationRequest",
  "ImageMetadata",
  "ResizeImageRequest",
  "SelectAssetRequest",
  "VideoMetadata",
  "GenerateSceneNarrativesRequest",
  "GenerateSceneNarrativesResponse",
  "FileMetadata",
]
