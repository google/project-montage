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

"""Render final video tool."""

from dataclasses import dataclass
from logging import Logger
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from schemas import VideoMetadata
from services.video_service import render_final_video_service


@dataclass
class RenderFinalVideoRequest:
  """Request schema for the `render_final_video` tool.

  Combines an optional BGM track, optional voiceover, and optional ASS
  subtitle burn-in into a single rendered video in one pass.
  """

  video_gcs_uri: Annotated[
    str,
    Field(description="GCS URI of the base video to render against."),
  ]
  bgm_gcs_uri: Annotated[
    str,
    Field(
      description="Optional GCS URI of a background music track (typically from generate_bgm). Looped and mixed under the voiceover when present."  # noqa: E501
    ),
  ] = ""
  voiceover_gcs_uri: Annotated[
    str,
    Field(
      description="Optional GCS URI of a stitched voiceover track (typically from generate_voiceover). Mixed on top of BGM/video audio."  # noqa: E501
    ),
  ] = ""
  ass_content: Annotated[
    str,
    Field(
      description="Optional raw ASS subtitle content to burn into the video. Pass the ass_content returned by generate_narrative."  # noqa: E501
    ),
  ] = ""
  audio_ducking: Annotated[
    bool,
    Field(
      description="Whether to duck BGM/video audio under the voiceover using sidechain compression. Set false for normal audio mixing."  # noqa: E501
    ),
  ] = True


def register_render_final_video_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the render final video tool on the provided MCP server."""

  @mcp.tool()
  async def render_final_video(
    request: RenderFinalVideoRequest,
  ) -> VideoMetadata:
    """
    Renders a finished video by muxing optional BGM, voiceover, and subtitles in one pass.

    Apply layers in order on the input video: background music (looped to length, replaces ambient audio), voiceover (mixed on top), then subtitle burn-in. Loudness is normalised once at the end. All three layer inputs are optional but at least one should be supplied -- otherwise the tool just re-encodes the input video.

    Args:
        request: A RenderFinalVideoRequest object containing:
                 - video_gcs_uri: GCS URI of the base video.
                 - bgm_gcs_uri: Optional BGM track from `generate_bgm`.
                 - voiceover_gcs_uri: Optional voiceover track from
                   `generate_voiceover`.
                 - ass_content: Optional raw ASS subtitle content from
                   `generate_narrative`. Pass the same `ass_content` that was
                   used to produce the voiceover so subtitles stay in sync.
                 - audio_ducking: Whether to duck BGM/video audio under the
                   voiceover. Defaults to true.

    Returns:
      A VideoMetadata that contains:
        - gcs_uri: GCS URI of the rendered video.
        - authenticated_url: URL where the user can view the final video.
        - duration_seconds: Duration of the final video in seconds.

    Response: The response must explicitly direct the user to the `authenticated_url` to view the resulted video.
    """  # noqa: E501

    logger.info("Invoking render_final_video tool.")

    return await render_final_video_service(
      video_gcs_uri=request.video_gcs_uri,
      bucket_name=bucket_name,
      bgm_gcs_uri=request.bgm_gcs_uri or None,
      voiceover_gcs_uri=request.voiceover_gcs_uri or None,
      ass_content=request.ass_content or None,
      audio_ducking=request.audio_ducking,
    )
