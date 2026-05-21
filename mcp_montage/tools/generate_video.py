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

"""Generate video tool."""

import asyncio
from dataclasses import asdict
from logging import Logger

from mcp.server.fastmcp import FastMCP
from schemas import (
  VideoGenerationRequest,
  VideoMetadata,
)
from services.video_service import (
  generate_video_service,
)


def register_generate_video_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the generate video tool on the provided MCP server."""

  @mcp.tool()
  async def generate_videos(
    requests: list[VideoGenerationRequest],
  ) -> list[VideoMetadata]:
    """
    Generate videos from first-frame images using Veo model. Supports parallel generation of multiple requests.

    Args:
      requests: A list of VideoGenerationRequest objects.
                Each object contains:
                - gcs_uri: GCS URI of the first-frame image used for the video.
                - prompt (string): A text prompt describing a video.
                - aspect_ratio: Aspect ratio of output video (e.g., '16:9', '9:16', '1:1'). Default to 16:9
                - duration_seconds (int): Desired duration of the generated video in seconds. Must be 4, 6, or 8. (default is 6)

    Returns:
      A list of video metadata that contains:
        - gcs_uri: GCS URI of the resulted video.
        - authenticated_url: URL of the resulted video where user can view.

    Response: The response must explicitly direct the user to the `authenticated_url` to view the resulted video.
    """  # noqa: E501

    logger.info("Invoking generate_video tool.")
    logger.info(f"Received {len(requests)} video generation requests.")

    videos: list[VideoMetadata] = await asyncio.gather(
      *[generate_video_service(**asdict(req)) for req in requests]
    )

    logger.info(f"Done generating videos: {videos}")
    return videos
