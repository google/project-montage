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

"""Image generation service module."""

from typing import Any

from google.genai import types
from schemas import ImageMetadata
from utils import log

from services.agents.config.prompt_loader import (  # noqa: E501
  generate_image_constraints_nanobanana_prompt,
)
from services.agents.factory import AgentFactory
from services.agents.image_agent import GeminiImageAgent
from services.agents.text_agent import GeminiAgent

logger = log.get_logger()


async def generate_image_service(
  visual_description: str,
  reference_images: list[dict[str, Any]] | None = None,
  aspect_ratio: str = "16:9",
  output_dir: str | None = None,
  output_gcs_uri: str | None = None,
) -> ImageMetadata:
  """Generate an image using the two-step agent workflow.

  This service implements a workflow similar to generate_video_service:
  1. Calls image_prompt_builder text agent with base image, and ingredient
     images to generate an appropriate prompt.
  2. Uses the returned image_prompt and selected images to call the
     image_generation agent to produce the final image.

  Args:
    visual_description: A brief text input from the user describing the desired image.
    reference_images: Reference images that MUST be referenced in the final prompt.
    aspect_ratio: Aspect ratio of output image (e.g., '16:9', '9:16', '1:1'). Default to 16:9
    output_dir: Optional local directory to save output images.
    output_gcs_uri: GCS URI to save output images.

  Returns:
    An ImageMetadata object that contains:
      - gcs_uri: GCS URI of the generated image.
      - authenticated_url: URL of the generated image where user can view the image.
      - image_description: Description of what the generated image looks like.
  """  # noqa: E501
  logger.info(f"Starting image generation for: {reference_images}")

  # Step 1: Download base image and prepare contents for prompt builder
  if reference_images:
    image_contents: types.ContentUnionDict = ["reference_images:"]
    for img in reference_images:
      image_contents.extend(
        ImageMetadata(
          gcs_uri=img["gcs_uri"],
          image_description=img.get("image_description", ""),
        ).to_contents()
      )
  else:
    image_contents = []

  contents: types.ContentUnionDict = [
    f"visual_description: {visual_description}",
    *image_contents,
  ]

  # Step 2: Call image_prompt_builder text agent
  image_prompt_builder_agent: GeminiAgent = AgentFactory.create_text_agent(
    agent_name="image_prompt_builder"
  )
  image_prompt = await image_prompt_builder_agent.generate_content_async(
    contents=contents
  )

  logger.info(f"Generated image prompt: {image_prompt}")

  image_prompt = (
    image_prompt + "\n\n" + generate_image_constraints_nanobanana_prompt
  )

  # Step 3: Call image_generation agent to generate the final image
  image_agent: GeminiImageAgent = AgentFactory.create_image_agent()

  # Build contents for image generation
  generation_contents: types.ContentUnionDict = [
    image_prompt,
    *image_contents,
  ]

  # Generate the image
  output_uris = await image_agent.generate_images(
    contents=generation_contents,
    aspect_ratio=aspect_ratio,
    output_dir=output_dir,
    output_gcs_uri=output_gcs_uri,
  )

  if output_uris:
    logger.info(f"Image generation completed. Output saved to {output_uris}")
  else:
    logger.error("Image generation failed: no output was created.")

  return await ImageMetadata.create(
    gcs_uri=output_uris[0], image_description=image_prompt
  )
