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

"""generate storyboard tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import Logger
from typing import Annotated

from google.genai import types
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from schemas import ImageMetadata, Storyboard
from services.agents.factory import AgentFactory
from services.agents.text_agent import GeminiAgent


@dataclass
class StoryBoardGenerationRequest:
  """Request schema for the storyboard generation tools."""

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
  domain_constraints: Annotated[
    str,
    Field(
      description="Optional domain-specific constraints appended to the storyboard prompt. Leave empty for general-purpose use."  # noqa: E501
    ),
  ] = ""

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

    if self.domain_constraints:
      prompt_parts.append(f"## **Constraints:** {self.domain_constraints}")

    return prompt_parts


def register_generate_storyboard_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the generate_storyboard_by_text tool on the provided MCP server."""  # noqa: E501

  @mcp.tool()
  async def generate_storyboard_by_text(
    request: StoryBoardGenerationRequest,
  ) -> Storyboard:
    """
    Generates a video storyboard consisting of multiple scenes based on user's context.

    Args:
      request: A StoryBoardGenerationByTextRequest object containing:
        - user_context: User-provided information related to the video. This also includes previously generated storyboard for editing.
        - duration_seconds: The total desired running time for the final video. Maximum is 60 seconds.

    Returns:
      A Storyboard object with the global style and an ordered list of scenes.
    """  # noqa: E501

    logger.info("Invoking generate_storyboard_by_text tool.")

    storyboard_writer_agent: GeminiAgent = AgentFactory.create_text_agent(
      agent_name="storyboard_writer"
    )
    storyboard_json = await storyboard_writer_agent.generate_json_content_async(
      contents=request.to_contents()
    )
    storyboard = Storyboard.from_dict(storyboard_json)

    logger.info(f"Done generating storyboard: {storyboard}")

    return storyboard

  @mcp.tool()
  async def generate_storyboard_by_image(
    request: StoryBoardGenerationRequest,
  ) -> Storyboard:
    """
    Generates a video storyboard consisting of multiple scenes based on user's requirements and images.

    Args:
      request: A StoryBoardGenerationRequest object containing:
        - user_context: User-provided information related to the video.
        - duration_seconds: The total desired running time for the final video. Maximum is 60 seconds.
        - source_images: List of user-provided images (scene backgrounds, locations, etc.).
        - asset_images: List of assets images.

    Returns:
      A Storyboard object with the global style and an ordered list of scenes.
    """  # noqa: E501

    logger.info("Invoking generate_storyboard_by_image tool.")

    storyboard_writer_agent: GeminiAgent = AgentFactory.create_text_agent(
      agent_name="image_to_storyboard_writer"
    )
    storyboard_json = await storyboard_writer_agent.generate_json_content_async(
      contents=request.to_contents()
    )
    storyboard = Storyboard.from_dict(storyboard_json)

    logger.info(f"Done generating storyboard: {storyboard}")

    return storyboard
