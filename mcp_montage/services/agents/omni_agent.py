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

import asyncio
import base64
import io
from typing import Any, Literal

from google.genai import types
from schemas.media import RawMediaItem
from shared.config import config
from shared.constants import GOOGLE_GENAI_USE_VERTEXAI
from utils import log
from utils import storage as storage_utils

from services.agents import base_agent

logger = log.get_logger()

_OMNI_SUPPORT_ASPECT_RATIOS = Literal["16:9", "9:16"]
_OMNI_SUPPORT_MAXIMUM_IMAGE_COUNT = 6


class OmniAgent(base_agent.BaseAgent):
  def __init__(
    self,
    agent_name: str = "Gemini Omni model",
    model_name: str = config.get(
      "gemini_omni_model", "gemini-omni-flash-preview"
    ),
    model_config: dict[str, Any] | None = None,
    automatic_function_calling: bool = False,
  ) -> None:
    if model_config is None:
      model_config = {}
    super().__init__(
      agent_name=agent_name,
      model_name=model_name,
      model_config=model_config,
      automatic_function_calling=automatic_function_calling,
    )

  async def generate_video(
    self,
    text: str,
    image_gcs_uris: list[str],
    output_dir: str,
    aspect_ratio: _OMNI_SUPPORT_ASPECT_RATIOS = "16:9",
    output_gcs_uri: str | None = None,
  ) -> str:
    logger.info(f"Executing generate video using {self.model_name}")

    if len(image_gcs_uris) > _OMNI_SUPPORT_MAXIMUM_IMAGE_COUNT:
      raise ValueError(
        "Too many images provided. Maximum number of images is "
        f"{_OMNI_SUPPORT_MAXIMUM_IMAGE_COUNT}."
      )

    if not text:
      raise ValueError("Text prompt is required for video generation.")

    logger.info(f"Processing {len(image_gcs_uris)} images.")

    logger.info(
      f"Creating video using {self.model_name} with aspect ratio {aspect_ratio}"
    )

    inputs: list[dict[str, Any]] = []
    for image_gcs_uri in image_gcs_uris:
      uri, mime_type = await self._resolve_media_uri(image_gcs_uri, "image/png")
      inputs.append({"type": "image", "uri": uri, "mime_type": mime_type})
    if text:
      inputs.append({"type": "text", "text": text})

    interaction = await self.genai_client.aio.interactions.create(
      model=self.model_name,
      input=inputs,
      response_format={
        "type": "video",
        "aspect_ratio": aspect_ratio,
      },
      timeout=600,
    )

    return await self._process_and_save_interaction_output(
      interaction=interaction,
      output_dir=output_dir,
      output_gcs_uri=output_gcs_uri,
    )

  async def edit_video(
    self,
    text: str,
    video_gcs_uri: str,
    output_dir: str,
    aspect_ratio: _OMNI_SUPPORT_ASPECT_RATIOS = "16:9",
    output_gcs_uri: str | None = None,
  ) -> str:
    logger.info(f"Executing stateful video editing using {self.model_name}")

    if not text:
      raise ValueError("Text prompt is required for video editing.")

    logger.info(
      f"Editing video: {video_gcs_uri} with text prompt: {text} | "
      f"Aspect ratio: {aspect_ratio}"
    )

    video_uri, video_mime_type = await self._resolve_media_uri(
      video_gcs_uri, "video/mp4"
    )
    inputs: list[dict[str, Any]] = [
      {"type": "video", "uri": video_uri, "mime_type": video_mime_type},
      {"type": "text", "text": text},
    ]

    interaction = await self.genai_client.aio.interactions.create(
      model=self.model_name,
      input=inputs,
    )

    return await self._process_and_save_interaction_output(
      interaction=interaction,
      output_dir=output_dir,
      output_gcs_uri=output_gcs_uri,
    )

  async def _resolve_media_uri(
    self, gcs_uri: str, mime_type: str
  ) -> tuple[str, str]:
    """Resolve a gs:// URI into a URI the Interactions API can read.

    Vertex AI's backend can dereference gs:// URIs directly, but the public
    Gemini API cannot: the media must be uploaded via the Files API first
    and referenced by the returned file URI, or the request is rejected
    with `400 invalid_argument`.
    """
    if GOOGLE_GENAI_USE_VERTEXAI:
      return gcs_uri, mime_type

    data = storage_utils.download_bytes_from_gcs(gcs_uri)
    uploaded_file = await self.genai_client.aio.files.upload(
      file=io.BytesIO(data),
      config=types.UploadFileConfig(mime_type=mime_type),
    )
    uploaded_file = await self._wait_for_file_active(uploaded_file)
    return uploaded_file.uri, uploaded_file.mime_type or mime_type

  async def _wait_for_file_active(
    self,
    file_obj: Any,
    poll_interval: float = 2.0,
    max_attempts: int = 60,
  ) -> Any:
    """Poll a Files API upload until it leaves the PROCESSING state."""
    attempt = 0
    while attempt < max_attempts:
      state = getattr(file_obj, "state", None)
      state_name = getattr(state, "name", str(state))
      if state_name == "ACTIVE":
        return file_obj
      if state_name == "FAILED":
        raise Exception(
          f"Files API upload failed to process: {getattr(file_obj, 'name', '')}"  # noqa: E501
        )
      await asyncio.sleep(poll_interval)
      file_obj = await self.genai_client.aio.files.get(name=file_obj.name)
      attempt += 1
    raise TimeoutError(
      f"Files API upload did not become ACTIVE in time: {getattr(file_obj, 'name', '')}"  # noqa: E501
    )

  async def _process_and_save_interaction_output(
    self,
    interaction: Any,
    output_dir: str,
    output_gcs_uri: str | None = None,
  ) -> str:
    """Helper to extract video bytes from interaction and save to GCS."""
    output_video = getattr(interaction, "output_video", None)
    if not output_video:
      raise Exception(
        f"No video generated by Omni model ({self.model_name}). "
        f"Status: {getattr(interaction, 'status', 'unknown')}, "
      )

    video_bytes: bytes | None = None
    video_mime_type: str = getattr(output_video, "mime_type", "video/mp4")

    if getattr(output_video, "data", None):
      video_bytes = base64.b64decode(output_video.data)
    elif getattr(output_video, "uri", None):
      video_bytes = await self.genai_client.aio.files.download(
        file=output_video.uri
      )

    if not video_bytes:
      raise Exception("No video bytes returned from Omni interaction output.")

    logger.info("Saving video output")

    gcs_uris: list[str] = storage_utils.save_media_batch(
      media_items=[RawMediaItem(data=video_bytes, mime_type=video_mime_type)],
      output_dir=output_dir,
      output_gcs_uri=output_gcs_uri,
      file_prefix="video",
    )
    return gcs_uris[0]
