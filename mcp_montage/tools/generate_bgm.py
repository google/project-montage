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

"""Generate BGM tool."""

from dataclasses import dataclass
from logging import Logger
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from schemas import AudioMetadata
from services.audio_service import generate_bgm_service


@dataclass
class GenerateBGMRequest:
  """Request schema for the `generate_bgm` tool."""

  video_gcs_uri: Annotated[
    str,
    Field(
      description="GCS URI of the video the BGM should be scored against. Used as a reference for the music prompt; the video itself is not modified."  # noqa: E501
    ),
  ]
  prompt: Annotated[
    str, Field(description="Optional text prompt for music generation.")
  ] = ""
  domain_constraints: Annotated[
    str,
    Field(
      description="Optional domain-specific constraints appended to all Gemini calls in this tool. Leave empty for general-purpose use."  # noqa: E501
    ),
  ] = ""


def register_generate_bgm_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the generate BGM tool on the provided MCP server."""

  @mcp.tool()
  async def generate_bgm(
    request: GenerateBGMRequest,
  ) -> AudioMetadata:
    """
    Generates background music for a video and returns the audio track.

    This tool only produces the music; muxing it into the video is the job of `render_final_video`. Pair them together (or with `generate_voiceover`) so all audio/subtitle layers are merged in a single render pass.

    Args:
        request: A GenerateBGMRequest object containing:
                 - video_gcs_uri: GCS URI of the video to score against.
                 - prompt: Optional text prompt for music generation.

    Returns:
      An AudioMetadata that contains:
        - gcs_uri: GCS URI of the generated BGM track.
        - authenticated_url: URL where the user can listen to the track.
        - duration_seconds: Duration of the BGM in seconds.
    """  # noqa: E501

    logger.info("Invoking generate_bgm tool.")

    return await generate_bgm_service(
      video_gcs_uri=request.video_gcs_uri,
      prompt=request.prompt,
      bucket_name=bucket_name,
      domain_constraints=request.domain_constraints,
    )
