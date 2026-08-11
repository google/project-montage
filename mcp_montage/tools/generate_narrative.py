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

"""Generate Narrative tool."""

from dataclasses import dataclass
from logging import Logger
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from schemas import Narrative
from services.video_service import (
  generate_narrative as generate_narratives_service,
)


@dataclass
class GenerateNarrativeRequest:
  """Request schema for the `generate_narrative` tool."""

  video_gcs_uri: Annotated[
    str, Field(description="GCS URI of the video to generate narration for.")
  ]
  prompt: Annotated[
    str,
    Field(
      description="Optional text prompt guiding the narration style and content."  # noqa: E501
    ),
  ] = ""
  storyboard: Annotated[
    str,
    Field(
      description="Optional storyboard JSON-as-string produced by `generate_storyboard_by_text` / `generate_storyboard_by_image`. Passed to Gemini so dialogue timing and content stay anchored to each scene."  # noqa: E501
    ),
  ] = ""
  domain_constraints: Annotated[
    str,
    Field(
      description="Optional domain-specific constraints appended to all Gemini calls in this tool. Leave empty for general-purpose use."  # noqa: E501
    ),
  ] = ""


def register_generate_narrative_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the generate scene narratives tool on the provided MCP server."""

  @mcp.tool()
  async def generate_narrative(
    request: GenerateNarrativeRequest,
  ) -> Narrative:
    """
    Generates a narration script for a video scene in raw ASS and readable formats.

    The returned `ass_content` is the input contract for `generate_voiceover` and the subtitle layer of `render_final_video` -- pass the same string to both so dialogue timings line up with the burned-in subtitles. The returned `voice_profile` is the voice-casting selection chosen with the video/storyboard context -- pass it to `generate_voiceover` so the voice fits the video instead of being picked from the bare script.

    Args:
        request: A GenerateNarrativeRequest object containing:
                 - video_gcs_uri: GCS URI of the video to generate narration for.
                 - prompt: Optional text prompt guiding the narration style and content.
                 - storyboard: Optional storyboard JSON-as-string from the storyboard generation step; supplying it helps the narration stay aligned with each scene's intent and timing.

    Returns:
      A Narrative object containing:
        - ass_content: Raw ASS subtitle content.
        - readable_content: Timestamp/text pairs parsed from the ASS dialogue.
        - romanization: Romanized (lowercase ASCII) transcription of each
          Dialogue line, one entry per line in order. Pass it to
          `generate_voiceover` so forced alignment works for
          non-Latin-script languages.
        - voice_profile: Voice-casting selection chosen with the
          video/storyboard context. Pass it to `generate_voiceover`.
    """  # noqa: E501
    logger.info("Invoking generate_narrative tool.")

    narrative_response = await generate_narratives_service(
      video_gcs_uri=request.video_gcs_uri,
      prompt=request.prompt,
      storyboard=request.storyboard,
      domain_constraints=request.domain_constraints,
    )

    logger.info("Done generating narrative content.")
    return narrative_response
