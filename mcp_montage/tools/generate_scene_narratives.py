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

"""Generate Scene Narratives tool."""

from logging import Logger

from mcp.server.fastmcp import FastMCP
from schemas import (
  GenerateSceneNarrativesRequest,
  GenerateSceneNarrativesResponse,
)
from services.video_service import (
  generate_scene_narratives as generate_narratives_service,
)


def register_generate_scene_narratives_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the generate scene narratives tool on the provided MCP server."""

  @mcp.tool()
  async def generate_scene_narratives(
    request: GenerateSceneNarrativesRequest,
  ) -> GenerateSceneNarrativesResponse:
    """
    Generates a narration script (SRT) for a video scene using Gemini.

    Args:
        request: A GenerateSceneNarrativesRequest object containing:
                 - video_gcs_uri: GCS URI of the video to generate narration for.
                 - prompt: Optional text prompt guiding the narration style and content.

    Returns:
      A GenerateSceneNarrativesResponse object containing:
        - srt_file: FileMetadata for the generated .srt file.
        - video: VideoMetadata for the video with embedded subtitles.
    """  # noqa: E501
    logger.info("Invoking generate_scene_narratives tool.")

    narrative_response = await generate_narratives_service(
      video_gcs_uri=request.video_gcs_uri,
      prompt=request.prompt,
    )

    logger.info(
      f"Done generating narrative: {narrative_response.srt_file.gcs_uri}"
    )
    logger.info(f"Subtitled video: {narrative_response.video.gcs_uri}")
    return narrative_response
