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

from dataclasses import dataclass, field
from typing import Annotated

from google.genai import types
from pydantic import Field

from schemas import ImageMetadata


@dataclass
class StoryBoardGenerationRequest:
  """Request schema for storyboard generation."""

  duration_seconds: Annotated[
    int,
    Field(
      description="The total desired time for the final video (seconds). Maximum is 60 seconds. If this value is not explicitly defined by the user, assume a default duration of 6 seconds for each source image or scene."  # noqa: E501
    ),  # noqa: E501
  ]
  user_context: Annotated[
    str,
    Field(
      description="User-provided information related to the video. This also includes previously generated storyboard for editing.",  # noqa: E501
    ),
  ] = "Generate a promotional video."
  source_images: Annotated[
    list[ImageMetadata],
    Field(
      description="List of user-provided images (scene backgrounds, etc.)."
    ),
  ] = field(default_factory=list)
  asset_images: Annotated[
    list[ImageMetadata],
    Field(
      description="List of character images from Asset Selection (with metadata and descriptions)."  # noqa: E501
    ),
  ] = field(default_factory=list)

  def __post_init__(self):
    """Validate and enforce constraints after initialization."""
    if self.duration_seconds > 60:
      self.duration_seconds = 60

  def to_contents(self) -> types.ContentUnionDict:
    """Converts the request object into a formatted string for the LLM."""
    prompt_parts: types.ContentUnionDict = [
      f"**User Context:** {self.user_context}",
      f"**Target Duration:** {self.duration_seconds} seconds",
    ]

    if self.source_images:
      prompt_parts.append("## **Source Images:**")
      for img in self.source_images:
        prompt_parts.extend(img.to_contents())

    if self.asset_images:
      prompt_parts.append("## **Assets Images:**")
      for img in self.asset_images:
        prompt_parts.extend(img.to_contents())

    return prompt_parts
