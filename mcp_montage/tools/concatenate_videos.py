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

from dataclasses import asdict, dataclass, field
from logging import Logger
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from schemas import VideoMetadata
from services.video_service import (
  concatenate_videos as concatenate_videos_wo_transition,
)
from services.video_service import (
  concatenate_videos_with_transition,
)


@dataclass
class ConcatenateVideosRequest:
  """Request schema for the `concatenate_videos` tool."""

  video_gcs_uris: Annotated[
    list[str],
    Field(
      description="Sequential list of GCS URIs for video paths. The first video is the first scene, the second video is the second scene, and so on."  # noqa: E501
    ),
  ]
  transition: Annotated[
    str,
    Field(
      description="""Type of transition effect between videos. Default to 'fade'. If you don't want any transition, use 'none'. Pick one from the following:
'none'
'fade'
'wipeleft'
'wiperight'
'wipeup'
'wipedown'
'slideleft'
'slideright'
'slideup'
'slidedown'
'circlecrop'
'rectcrop'
'distance'
'fadeblack'
'fadewhite'
'radial'
'smoothleft'
'smoothright'
'smoothup'
'smoothdown'
'circleopen'
'circleclose'
'vertopen'
'vertclose'
'horzopen'
'horzclose'
'dissolve'
'pixelize'
'diagtl'
'diagtr'
'diagbl'
'diagbr'
'hlslice'
'hrslice'
'vuslice'
'vdslice'
'hblur'
'fadegrays'
'wipetl'
'wipetr'
'wipebl'
'wipebr'
'squeezeh'
'squeezev'
'zoomin'
'fadefast'
'fadeslow'
'hlwind'
'hrwind'
'vuwind'
'vdwind'
'coverleft'
'coverright'
'coverup'
'coverdown'
'revealleft'
'revealright'
'revealup'
'revealdown'"""  # noqa: E501
    ),
  ] = "fade"
  scene_durations: Annotated[
    list[float],
    Field(
      description="Net storyboard duration of each scene in seconds, in the same order as video_gcs_uris. Required whenever transition_buffer_seconds is non-zero."  # noqa: E501
    ),
  ] = field(default_factory=list)
  transition_buffer_seconds: Annotated[
    float,
    Field(
      description="Seconds of extra footage each clip was generated with for the transition to consume. Pass the storyboard's transition_buffer_seconds. Leave at 0.0 for clips generated without a buffer (e.g. by generate_videos), which supports only 'fade' and 'none'."  # noqa: E501
    ),
  ] = 0.0


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
                 - scene_durations: Net storyboard duration of each scene, in the same order as video_gcs_uris. Required when transition_buffer_seconds is non-zero.
                 - transition_buffer_seconds: The storyboard's transition_buffer_seconds. Clips generated without a buffer must leave this at 0.0 and use only 'fade' or 'none'.

    Returns:
      A video metadata that contains:
        - gcs_uri: GCS URI of the resulting video.
        - authenticated_url: URL of the resulting video where user can view.
        - duration_seconds: Duration of the resulting video in seconds.

    Response: The response must explicitly direct the user to the `authenticated_url` to view the resulting video.
    """  # noqa: E501

    logger.info("Invoking concatenate_videos tool.")
    logger.info(
      f"Received request to concatenate {len(request.video_gcs_uris)} videos."
    )

    if request.transition == "none":
      if request.transition_buffer_seconds > 0:
        logger.warning(
          f"transition='none' with a "
          f"{request.transition_buffer_seconds}s buffer: no transition "
          f"consumes the buffers, so the result runs roughly "
          f"{len(request.video_gcs_uris) * request.transition_buffer_seconds}s "  # noqa: E501
          f"longer than the storyboard total. Nothing compensates for this."
        )
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
