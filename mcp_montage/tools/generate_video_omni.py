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

"""Generate video omni tool."""

import asyncio
from dataclasses import asdict, dataclass
from logging import Logger
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from schemas import VideoMetadata
from services.omni_service import generate_video_omni_service


@dataclass
class OmniVideoGenerationRequest:
  """Request schema for the `generate_videos_omni` tool."""

  prompt: Annotated[
    str,
    Field(description="Text prompt describing the desired video."),
  ] = ""
  image_gcs_uri: Annotated[
    str,
    Field(
      description="GCS URI of the first-frame image used for the video generation."  # noqa: E501
    ),
  ] = ""
  aspect_ratio: Annotated[
    str,
    Field(
      description=(
        "Aspect ratio of output video ('16:9', '9:16'). Default to 16:9"
      )
    ),
  ] = "16:9"
  duration_seconds: Annotated[
    int,
    Field(
      description=(
        "Desired duration of the generated video in seconds. Default is 6"
      )
    ),
  ] = 6
  domain_constraints: Annotated[
    str,
    Field(
      description=(
        "Optional domain-specific constraints appended to Gemini call in"
        " this tool."
      )
    ),
  ] = ""


def register_generate_video_omni_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the generate video omni tool on the provided MCP server."""

  @mcp.tool()
  async def generate_videos_omni(
    requests: list[OmniVideoGenerationRequest],
  ) -> list[VideoMetadata]:
    """
    Generate videos from text prompts and input images using Gemini Omni model.

    Support parallel generation of multiple requests.

    Args:
      requests: A list of OmniVideoGenerationRequest objects.
                Each object contains:
                - prompt (string): A text prompt describing a video.
                - image_gcs_uri (string): GCS URI of the first-frame image used for video generation.
                - aspect_ratio: Aspect ratio of output video ('16:9' or '9:16'). Default to 16:9
                - duration_seconds (int): Desired duration of the generated video in seconds.
                - domain_constraints (string): Optional domain-specific constraints appended to Gemini call in this tool.

    Returns:
      A list of video metadata that contains:
        - gcs_uri: GCS URI of the resulting video.
        - authenticated_url: URL of the resulting video where user can view.

    Response: The response must explicitly direct the user to the `authenticated_url` to view the resulting video.
    """  # noqa: E501

    logger.info("Invoking generate_videos_omni tool.")
    logger.info(f"Received {len(requests)} video generation requests.")

    results = await asyncio.gather(
      *[
        generate_video_omni_service(
          **asdict(req), output_gcs_uri=f"gs://{bucket_name}/generated_videos"
        )
        for req in requests
      ],
      return_exceptions=True,
    )

    videos: list[VideoMetadata] = []
    for req, res in zip(requests, results, strict=True):
      if isinstance(res, Exception) or not isinstance(res, VideoMetadata):
        logger.error(f"Omni video generation failed for req: {req}: {res}")
        videos.append(
          VideoMetadata(
            gcs_uri="",
            duration_seconds=0.0,
            status="error",
            error=str(res),
          )
        )
      else:
        videos.append(res)

    logger.info(f"Done generating omni videos: {videos}")
    return videos
