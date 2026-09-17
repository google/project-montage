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

"""Omni model video generation services for Project Montage."""

from typing import Literal

from google.genai import types
from schemas import VideoMetadata
from utils import log
from utils.image import convert_image_to_part

from services.agents.factory import AgentFactory
from services.agents.text_agent import GeminiAgent

logger = log.get_logger()

_OMNI_VIDEO_TASKS = Literal[
  "text_to_video", "image_to_video", "reference_to_video", "edit"
]


async def generate_video_omni_service(
  output_gcs_uri: str,
  prompt: str = "",
  image_gcs_uri: str = "",
  duration_seconds: int = 6,
  aspect_ratio: Literal["16:9", "9:16"] = "16:9",
  domain_constraints: str = "",
  transition_buffer_seconds: float = 0.0,
  output_dir: str = "tests",
) -> VideoMetadata:
  """Generate a video from text prompt and an optional first frame image using Omni model."""  # noqa: E501

  if not prompt and not image_gcs_uri:
    raise ValueError(
      "Either prompt or image_gcs_uri must be provided for video generation."
    )

  logger.info(
    f"Queueing video generation for: '{image_gcs_uri}', prompt: '{prompt}'"
  )

  # Step 1: Use Gemini to generate a prompt for video generation

  contents: types.ContentUnionDict = []

  if (
    image_gcs_uri
    and image_gcs_uri.strip()
    and image_gcs_uri.strip() not in ('""', "''")
  ):
    contents.append(
      convert_image_to_part(image=image_gcs_uri, mime_type="image/png")
    )
    contents.append(
      "Instruction: The provided image is the first frame. The generated video must start from this exact image. Refer to it as <FIRST_FRAME> in the video prompt."  # noqa: E501
    )

  if prompt:
    contents.append(f"Text prompt: {prompt}")

  # Omni has no duration API parameter -- duration reaches the model only
  # as a [0-Xs] timecode built from this line, so the transition buffer is
  # added here. ":g" keeps 7.0 rendering as "7" rather than "7.0", which
  # the prompt builder turns into a cleaner timecode.
  gross_duration = duration_seconds + transition_buffer_seconds
  contents.append(f"Expected video duration: {gross_duration:g} seconds")

  if domain_constraints:
    contents.append(f"Constraints: {domain_constraints}")

  omni_prompt_builder_agent: GeminiAgent = AgentFactory.create_text_agent(
    agent_name="omni_video_prompt_builder"
  )
  resp: dict[
    str, str
  ] = await omni_prompt_builder_agent.generate_json_content_async(
    contents=contents
  )
  video_prompt: str = str(resp.get("video_prompt", "")).strip()

  logger.info(f"Generated video prompt: {video_prompt}")

  if domain_constraints:
    video_prompt = video_prompt + "\n\n" + domain_constraints

  # Step 2: Omni agent to generate a video from inputs
  omni_agent = AgentFactory.create_omni_agent()

  video_metadata: VideoMetadata = await omni_agent.generate_video(
    text=video_prompt,
    image_gcs_uris=[image_gcs_uri] if image_gcs_uri else [],
    aspect_ratio=aspect_ratio,
    output_dir=output_dir,
    output_gcs_uri=output_gcs_uri,
  )

  logger.info(
    f"Video generation completed. Output saved to {video_metadata.gcs_uri}"
  )

  return video_metadata


async def generate_video_with_references_omni_service(
  image_gcs_uris: list[str],
  output_gcs_uri: str,
  prompt: str = "",
  duration_seconds: int = 6,
  aspect_ratio: Literal["16:9", "9:16"] = "16:9",
  domain_constraints: str = "",
  transition_buffer_seconds: float = 0.0,
  output_dir: str = "",
) -> VideoMetadata:
  """Generate a video guided by reference images using the Omni model."""

  if not prompt and not image_gcs_uris:
    raise ValueError(
      "Either prompt or image_gcs_uris must be provided for reference video "
      "generation."
    )

  logger.info(
    "Queueing reference-guided video generation using Omni for: "
    f"{image_gcs_uris}, prompts: '{prompt}'"
  )

  # Step 1: Use Gemini to generate a prompt for video generation
  contents: types.ContentUnionDict = [
    "Reference images:",
    *[
      convert_image_to_part(image=gcs_uri, mime_type="image/png")
      for gcs_uri in image_gcs_uris
    ],
  ]

  if prompt:
    contents.append(f"Text prompt: {prompt}")

  # Omni has no duration API parameter -- duration reaches the model only
  # as a [0-Xs] timecode built from this line, so the transition buffer is
  # added here, mirroring generate_video_omni_service. ":g" keeps 7.0
  # rendering as "7" rather than "7.0".
  gross_duration = duration_seconds + transition_buffer_seconds
  contents.append(f"Expected video duration: {gross_duration:g} seconds")

  if domain_constraints:
    contents.append(f"Constraints: {domain_constraints}")

  omni_prompt_builder_agent: GeminiAgent = AgentFactory.create_text_agent(
    agent_name="omni_video_prompt_builder"
  )
  resp: dict[
    str, str
  ] = await omni_prompt_builder_agent.generate_json_content_async(
    contents=contents
  )
  video_prompt: str = str(resp.get("video_prompt", "")).strip()

  logger.info(f"Generated video prompt: {video_prompt}")

  if domain_constraints:
    video_prompt = video_prompt + "\n\n" + domain_constraints

  # Step 2: Omni agent to generate a video from inputs
  omni_agent = AgentFactory.create_omni_agent()

  video_metadata = await omni_agent.generate_video_from_references(
    text=video_prompt,
    image_gcs_uris=image_gcs_uris,
    aspect_ratio=aspect_ratio,
    output_dir=output_dir,
    output_gcs_uri=output_gcs_uri,
  )

  logger.info(
    f"Video generation completed. Output saved to {video_metadata.gcs_uri}"
  )

  return video_metadata
