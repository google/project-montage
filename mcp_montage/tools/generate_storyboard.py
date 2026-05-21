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

"""generate storyboard by text input"""

from __future__ import annotations

from logging import Logger

from mcp.server.fastmcp import FastMCP
from schemas import StoryBoardGenerationRequest
from services.agents.factory import AgentFactory
from services.agents.text_agent import GeminiAgent


def register_generate_storyboard_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the generate_storyboard_by_text tool on the provided MCP server."""  # noqa: E501

  @mcp.tool()
  async def generate_storyboard_by_text(
    request: StoryBoardGenerationRequest,
  ) -> str:
    """
    Generates a video storyboard consisting of multiple scenes based on user's context.

    Args:
      request: A StoryBoardGenerationByTextRequest object containing:
        - user_context: User-provided information related to the video. This also includes previously generated storyboard for editing.
        - duration_seconds: The total desired running time for the final video. Maximum is 60 seconds.

    Returns:
      A string of storyboard object.
    """  # noqa: E501

    logger.info("Invoking generate_storyboard_by_text tool.")

    storyboard_writer_agent: GeminiAgent = AgentFactory.create_text_agent(
      agent_name="storyboard_writer"
    )
    storyboard = await storyboard_writer_agent.generate_content_async(
      contents=request.to_contents()
    )

    logger.info(f"Done generating storyboard: {storyboard}")

    return storyboard

  @mcp.tool()
  async def generate_storyboard_by_image(
    request: StoryBoardGenerationRequest,
  ) -> str:
    """
    Generates a video storyboard consisting of multiple scenes based on user's requirements and images.

    Args:
      request: A StoryBoardGenerationRequest object containing:
        - user_context: User-provided information related to the video.
        - duration_seconds: The total desired running time for the final video. Maximum is 60 seconds.
        - source_images: List of user-provided images (scene backgrounds, locations, etc.).
        - asset_images: List of assets images.

    Returns:
      A string of storyboard object.
    """  # noqa: E501

    logger.info("Invoking generate_storyboard_by_image tool.")

    storyboard_writer_agent: GeminiAgent = AgentFactory.create_text_agent(
      agent_name="image_to_storyboard_writer"
    )
    storyboard = await storyboard_writer_agent.generate_content_async(
      contents=request.to_contents()
    )

    logger.info(f"Done generating storyboard: {storyboard}")

    return storyboard
