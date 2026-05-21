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

"""Generate BGM and merge tool."""

from logging import Logger

from mcp.server.fastmcp import FastMCP
from schemas import (
  GenerateBGMAndMergeRequest,
  VideoMetadata,
)
from services.audio_service import generate_bgm_and_merge_service


def register_generate_bgm_and_merge_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the generate BGM and merge tool on the provided MCP server."""

  @mcp.tool()
  async def generate_bgm_and_merge(
    request: GenerateBGMAndMergeRequest,
  ) -> VideoMetadata:
    """
    Generates background music and merges it with the video.

    Args:
        request: A GenerateBGMAndMergeRequest object containing:
                 - video_gcs_uri: GCS URI of the video to add audio to.
                 - prompt: Optional text prompt for music generation.

    Returns:
      A video metadata that contains:
        - gcs_uri: GCS URI of the resulted video.
        - authenticated_url: URL of the resulted video where user can view.
        - duration_seconds: Duration of the resulted video in seconds.

    Response: The response must explicitly direct the user to the `authenticated_url` to view the resulted video.
    """  # noqa: E501

    logger.info("Invoking generate_bgm_and_merge tool.")

    return await generate_bgm_and_merge_service(
      video_gcs_uri=request.video_gcs_uri,
      prompt=request.prompt,
      bucket_name=bucket_name,
    )
