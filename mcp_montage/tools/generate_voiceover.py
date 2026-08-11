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

"""Generate voiceover tool."""

from dataclasses import dataclass
from logging import Logger
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from schemas import AudioMetadata, VoiceProfile
from services.speech_service import generate_voiceover_service


@dataclass
class GenerateVoiceoverRequest:
  """Request schema for the `generate_voiceover` tool."""

  ass_content: Annotated[
    str,
    Field(
      description="Raw ASS subtitle content. Dialogue timings drive the voiceover stitching so it lines up with later subtitle burn-in."  # noqa: E501
    ),
  ]
  voice_profile: Annotated[
    VoiceProfile | None,
    Field(
      description="Optional voice-casting selection. Pass the `voice_profile` returned by `generate_narrative` so the voice fits the video/storyboard context. When omitted, a voice is picked from `ass_content` alone."  # noqa: E501
    ),
  ] = None
  romanization: Annotated[
    list[str] | None,
    Field(
      description="Optional romanized transcript from `generate_narrative`: one lowercase-ASCII entry per ASS Dialogue line, in order. Pass it whenever it is available -- forced alignment needs it for any non-Latin-script narration; omitting it falls back to aligning on the raw dialogue text, which only works for English."  # noqa: E501
    ),
  ] = None


def register_generate_voiceover_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the generate voiceover tool on the provided MCP server."""

  @mcp.tool()
  async def generate_voiceover(
    request: GenerateVoiceoverRequest,
  ) -> AudioMetadata:
    """
    Generates a subtitle-aligned voiceover track from raw ASS subtitle content.

    The voiceover is synthesised once and then re-stitched so that each line lands at the timestamp its ASS dialogue line specifies. If a generated line overruns its scene window past tolerance, an internal refinement loop asks a narrative-refiner agent to shorten the offending lines and regenerates the whole voiceover (preserving voice consistency) up to a few times. When that happens, the response's `refined_ass_content` is the updated ASS that matches the returned voiceover -- you MUST pass that string (not the original ASS) to `render_final_video` so the burned-in subtitles stay in sync.

    Args:
        request: A GenerateVoiceoverRequest object containing:
                 - ass_content: Raw ASS subtitle content. Use the
                   `ass_content` returned by `generate_narrative`.
                 - voice_profile: Optional voice-casting selection. Pass the
                   `voice_profile` returned by `generate_narrative` so the
                   voice matches the video/storyboard context. Omit it to let
                   this tool pick a voice from `ass_content` alone.
                 - romanization: Optional romanized transcript from
                   `generate_narrative`: one lowercase-ASCII entry per ASS
                   Dialogue line, in order. Pass it whenever it is available
                   -- forced alignment needs it for any non-Latin-script
                   narration; omitting it falls back to aligning on the raw
                   dialogue text, which only works for English.

    Returns:
      An AudioMetadata that contains:
        - gcs_uri: GCS URI of the stitched voiceover WAV.
        - authenticated_url: URL where the user can listen to the track.
        - duration_seconds: Duration of the voiceover in seconds.
        - refined_ass_content: Refined ASS content when the refinement loop
          shortened one or more lines, otherwise None. When set, pass this
          to `render_final_video` instead of the original `ass_content`.
    """  # noqa: E501

    logger.info("Invoking generate_voiceover tool.")

    return await generate_voiceover_service(
      ass_content=request.ass_content,
      bucket_name=bucket_name,
      voice_profile=request.voice_profile,
      romanization=request.romanization,
    )
