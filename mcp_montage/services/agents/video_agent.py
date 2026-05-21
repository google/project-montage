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

"""Base class for Video generation model."""

import asyncio
from typing import Any

from google.genai import types
from PIL import Image
from schemas.media import RawMediaItem
from shared.config import config
from tenacity import retry, stop_after_attempt, wait_exponential
from utils import log
from utils import storage as storage_utils

from services.agents import base_agent

logger = log.get_logger()


class VeoAgent(base_agent.BaseAgent):
  """Video generation agent"""

  def __init__(
    self,
    agent_name: str = "Veo 3 video generation model",
    model_name: str = config.get("veo_model", "veo-3.1-fast-generate-001"),
    model_config: dict[str, Any] | None = None,
    automatic_function_calling: bool = False,
  ):
    if model_config is None:
      model_config = {}
    super().__init__(
      agent_name=agent_name,
      model_name=model_name,
      model_config=model_config,
      automatic_function_calling=automatic_function_calling,
    )

  async def save_generated_videos(
    self,
    operation: types.GenerateVideosOperation,
    output_dir: str,
    output_gcs_uri: str | None = None,
  ) -> list[str]:
    """Saves generated videos either locally or to GCS based on parameters."""

    # Waiting for the video(s) to be generated
    while not operation.done:
      await asyncio.sleep(15)
      logger.info("Waiting for the video(s) to be generated...")
      operation = await self.genai_client.aio.operations.get(operation)

    result = operation.result

    if not result:
      logger.error("Error occurred while generating video.")
      raise Exception("Error occurred while generating video.")

    generated_videos = result.generated_videos
    if not generated_videos:
      logger.error("No videos were generated.")
      raise Exception("No videos were generated.")

    video_items = []
    for generated_video in generated_videos:
      if generated_video.video:
        logger.info(f"Video has been generated: {generated_video.video}")

        video_bytes = None
        if generated_video.video.video_bytes:
          video_bytes = generated_video.video.video_bytes
        elif generated_video.video.uri:
          video_bytes = await self.genai_client.aio.files.download(
            file=generated_video.video.uri
          )

        if video_bytes:
          video_items.append(
            RawMediaItem(data=video_bytes, mime_type="video/mp4")
          )
      else:
        logger.debug(f"No video has been generated: {generated_video}")

    return storage_utils.save_media_batch(
      video_items,
      output_dir,
      output_gcs_uri,
      file_prefix="video",
    )

  @retry(
    wait=wait_exponential(min=10, max=60, multiplier=2),
    stop=stop_after_attempt(3),
  )
  async def text_to_videos(
    self,
    prompt: str,
    output_dir: str,
    number_of_videos: int = 2,
    negative_prompt: str = "",
    aspect_ratio: str = "16:9",
    fps: int = 24,
    duration_seconds: int = 8,
    output_gcs_uri: str | None = None,
    generate_audio: bool = False,
  ) -> list[str]:
    logger.info(f"Generating videos using {self.model_name}")
    logger.debug(self._build_request_log(prompt))

    operation: types.GenerateVideosOperation = await self.genai_client.aio.models.generate_videos(  # noqa: E501
      model=self.model_name,
      prompt=prompt,
      config=types.GenerateVideosConfig(
        # output_gcs_uri=output_gcs_uri if self.genai_client.vertexai else None,
        aspect_ratio=aspect_ratio,
        fps=fps if self.genai_client.vertexai else None,
        number_of_videos=number_of_videos,
        duration_seconds=duration_seconds,
        person_generation=("allow_all" if self.genai_client.vertexai else None),
        negative_prompt=negative_prompt,
        generate_audio=generate_audio if self.genai_client.vertexai else None,
      ),
    )

    return await self.save_generated_videos(
      operation,
      output_dir,
      output_gcs_uri,
    )

  def _process_image_bytes(
    self,
    image_bytes: bytes,
    target_aspect_ratio: float | None = None,
  ) -> tuple[types.Image, str, float]:
    import io

    with Image.open(io.BytesIO(image_bytes)) as img:
      width, height = img.size
      img_format = img.format.lower() if img.format else "png"
      # Ensure format is supported (PNG or JPEG), default to PNG otherwise
      if img_format not in ["png", "jpeg", "jpg"]:
        img_format = "png"

      if target_aspect_ratio is None:
        if width >= height:  # Landscape or square
          target_width_ratio = 16
          target_height_ratio = 9
        else:  # Portrait
          target_width_ratio = 9
          target_height_ratio = 16
        target_aspect_ratio = target_width_ratio / target_height_ratio
        aspect_ratio_str = f"{target_width_ratio}:{target_height_ratio}"
      else:
        aspect_ratio_str = ""  # Not used when target_aspect_ratio is provided

      # Padding logic
      new_width = width
      new_height = height
      padding_color = (0, 0, 0)

      current_aspect_ratio = width / height
      if current_aspect_ratio > target_aspect_ratio:
        # Image is too wide, need to add vertical padding (top/bottom)
        new_height = int(width / target_aspect_ratio)
        padding_needed_y = new_height - height
        pad_top = padding_needed_y // 2
        # pad_bottom = padding_needed_y - pad_top
        pad_left = 0
        # pad_right = 0
      else:
        # Image is too tall, need to add horizontal padding (left/right)
        new_width = int(height * target_aspect_ratio)
        padding_needed_x = new_width - width
        pad_left = padding_needed_x // 2
        # pad_right = padding_needed_x - pad_left
        pad_top = 0
        # pad_bottom = 0

      # Create a new image with the target dimensions and padding color
      new_img = Image.new(img.mode, (new_width, new_height), padding_color)

      # Paste the original image onto the center of the new image
      new_img.paste(img, (pad_left, pad_top))

      out_io = io.BytesIO()
      new_img.save(out_io, format=img_format.upper())
      out_bytes = out_io.getvalue()

      mime_type = f"image/{img_format}"
      if img_format == "jpg":
        mime_type = "image/jpeg"

      return (
        types.Image(image_bytes=out_bytes, mime_type=mime_type),
        aspect_ratio_str,
        target_aspect_ratio,
      )

  @retry(
    wait=wait_exponential(min=30, max=60, multiplier=2),
    stop=stop_after_attempt(3),
  )
  async def image_to_videos(
    self,
    first_frame_bytes: bytes,
    prompt: str,
    output_dir: str,
    number_of_videos: int = 2,
    negative_prompt: str = "",
    aspect_ratio: str = "16:9",
    fps: int = 24,
    duration_seconds: int = 8,
    last_frame_bytes: bytes | None = None,
    output_gcs_uri: str | None = None,
    generate_audio: bool = False,
  ) -> list[str]:
    logger.info(f"Generating videos using {self.model_name}")
    logger.debug(self._build_request_log(prompt))

    first_frame_img, aspect_ratio, target_ratio = self._process_image_bytes(
      first_frame_bytes,
    )

    last_frame_img = None
    if last_frame_bytes:
      last_frame_img, _, _ = self._process_image_bytes(
        last_frame_bytes,
        target_aspect_ratio=target_ratio,
      )

    operation: types.GenerateVideosOperation = (
      await self.genai_client.aio.models.generate_videos(  # noqa: E501
        model=self.model_name,
        prompt=prompt,
        image=first_frame_img,
        config=types.GenerateVideosConfig(
          aspect_ratio=aspect_ratio,
          fps=fps if self.genai_client.vertexai else None,
          number_of_videos=number_of_videos,
          duration_seconds=duration_seconds,
          person_generation=(
            "allow_all" if self.genai_client.vertexai else None
          ),
          negative_prompt=negative_prompt,
          generate_audio=generate_audio if self.genai_client.vertexai else None,
          last_frame=last_frame_img if self.genai_client.vertexai else None,
        ),
      )
    )

    video_output = await self.save_generated_videos(
      operation,
      output_dir,
      output_gcs_uri,
    )

    if video_output:
      logger.info(f"Video generation completed. Output saved to {video_output}")
      return video_output
    else:
      raise Exception(
        "Video generation failed: no output directory was created.",  # noqa: E501
      )
