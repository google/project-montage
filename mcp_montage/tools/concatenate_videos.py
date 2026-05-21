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

"""Concatenate videos tool."""

from dataclasses import asdict
from logging import Logger

from mcp.server.fastmcp import FastMCP
from schemas import (
  ConcatenateVideosRequest,
  VideoMetadata,
)
from services.video_service import (
  concatenate_videos as concatenate_videos_wo_transition,
)
from services.video_service import (
  concatenate_videos_with_transition,
)


def register_concatenate_videos_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the concatenate videos tool on the provided MCP server."""

  @mcp.tool()
  def concatenate_videos(
    request: ConcatenateVideosRequest,
  ) -> VideoMetadata:
    """
    Concatenate multiple video clips into a single sequence.

    Args:
        request: A ConcatenateVideosRequest object containing:
                 - video_gcs_uris: Sequential list of GCS URIs for video paths. The first video is the first scene, the second video is the second scene, and so on.
                 - transition: Type of transition effect between videos. Default to 'fade'.

    Returns:
      A video metadata that contains:
        - gcs_uri: GCS URI of the resulted video.
        - authenticated_url: URL of the resulted video where user can view.
        - duration_seconds: Duration of the resulted video in seconds.

    Response: The response must explicitly direct the user to the `authenticated_url` to view the resulted video.
    """  # noqa: E501

    logger.info("Invoking concatenate_videos tool.")
    logger.info(
      f"Received request to concatenate {len(request.video_gcs_uris)} videos."
    )

    if request.transition == "none":
      video: VideoMetadata = concatenate_videos_wo_transition(
        video_gcs_uris=request.video_gcs_uris,
        output_gcs_uri=f"gs://{bucket_name}/concatenated_videos",
      )
    else:
      video: VideoMetadata = concatenate_videos_with_transition(
        **asdict(request),
        output_gcs_uri=f"gs://{bucket_name}/concatenated_videos",
      )
    logger.info(f"Done concatenating videos: {video}")

    return video
