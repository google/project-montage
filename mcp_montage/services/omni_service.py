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

from typing import Literal

from google.genai import types
from schemas import VideoMetadata
from utils import log
from utils.image import convert_image_to_part

from services.agents.factory import AgentFactory
from services.agents.text_agent import GeminiAgent

logger = log.get_logger()


async def generate_video_omni_service(
  output_gcs_uri: str,
  prompt: str = "",
  image_gcs_uri: str = "",
  duration_seconds: int = 6,
  aspect_ratio: Literal["16:9", "9:16"] = "16:9",
  domain_constraints: str = "",
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

  contents.append(f"Expected video duration: {duration_seconds} seconds")

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

  uploaded_uri = await omni_agent.generate_video(
    text=video_prompt,
    image_gcs_uris=[image_gcs_uri] if image_gcs_uri else [],
    aspect_ratio=aspect_ratio,
    output_dir=output_dir,
    output_gcs_uri=output_gcs_uri,
  )

  logger.info(f"Video generation completed. Output saved to {uploaded_uri}")

  return VideoMetadata(uploaded_uri, duration_seconds=duration_seconds)
