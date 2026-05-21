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

"""Contains business logic for audio processing and BGM generation."""

import os

from google.genai import types
from schemas import VideoMetadata
from utils import log
from utils.ffmpeg import FfmpegRunner
from utils.image import convert_image_to_part

from services import lyria_service
from services.agents.factory import AgentFactory

logger = log.get_logger()


async def generate_bgm_music(
  video_gcs_uri: str,
  prompt: str | None = None,
  local_dir: str | None = None,
) -> str:
  """Generates BGM music using the Lyria API.

  Args:
      video_gcs_uri: GCS URI of the video to generate BGM for.
      prompt: (Optional) Additional prompt for the music.
      local_dir: (Optional) Local directory to save the generated music.

  Returns:
      Path to the normalized BGM file.
  """
  # Generate BGM prompt using IAgent
  music_prompt_builder_agent = AgentFactory.create_text_agent(
    "music_prompt_builder",
  )

  user_prompt_parts: types.ContentUnionDict = [
    "Video:",
    convert_image_to_part(image=video_gcs_uri, mime_type="video/mp4"),
  ]

  if prompt:
    user_prompt_parts.append(prompt)

  response_json = await music_prompt_builder_agent.generate_json_content_async(
    user_prompt_parts,
  )
  logger.info(f"Generated background music prompt: {response_json}")

  try:
    music_description = response_json["answer"]
  except Exception as e:
    raise ValueError(
      "Cannot load json response from music prompt builder"
    ) from e  # noqa: E501

  # Generate BGM music using Lyria Service
  try:
    output_bgm_path = await lyria_service.generate_music(
      prompt=music_description,
      local_dir=local_dir,
    )
  except Exception as e:
    raise ValueError(f"Lyria Service Error: {e}") from e

  # Normalize Loudness
  try:
    norm_output_bgm_path = normalize_loudness(
      input_file=output_bgm_path,
      target_i=-23.0,
      target_lra=7.0,
      target_tp=-2.0,
    )
  except Exception as e:
    raise ValueError(f"Normalized BGM Error: {e}") from e

  return norm_output_bgm_path


def normalize_loudness(
  input_file: str,
  target_i: float = -23.0,
  target_lra: float = 7.0,
  target_tp: float = -2.0,
  sample_rate: int = 48000,
  audio_bitrate: str = "500k",
  audio_channels: int = 6,
) -> str:
  """Normalizes video audio loudness using FfmpegRunner.

  Args:
      input_file (str): Path to the input video file.
      target_i (float): Target integrated loudness (LUFS). Default: -23.0.
      target_lra (float): Target loudness range (LU). Default: 7.0.
      target_tp (float): Target true peak (dBTP). Default: -2.0.
      sample_rate (int): Output audio sample rate (Hz). Default: 48000.
      audio_bitrate (str): Output audio bitrate (e.g., '500k'). Default: "500k".
      audio_channels (int): Number of output audio channels. Default: 6.

  Returns:
      str: The path to the normalized output file if successful
  """

  ffmpeg = FfmpegRunner()
  return ffmpeg.normalize_loudness(
    input_file=input_file,
    target_i=target_i,
    target_lra=target_lra,
    target_tp=target_tp,
    sample_rate=sample_rate,
    audio_bitrate=audio_bitrate,
    audio_channels=audio_channels,
  )


async def generate_bgm_and_merge_service(
  video_gcs_uri: str,
  prompt: str | None = None,
  bucket_name: str | None = None,
) -> VideoMetadata:
  """Generates background music and merges it with the video.

  Args:
      video_gcs_uri: GCS URI of the video to add audio to.
      prompt: Optional text prompt for music generation.
      bucket_name: Optional GCS bucket name for uploading the result.

  Returns:
      VideoMetadata: Metadata of the resulting video with BGM.
  """
  import tempfile
  import time

  from schemas import VideoMetadata
  from schemas.media import RawMediaItem
  from shared.constants import GCS_BUCKET_NAME
  from utils.storage import download_blob_to_file, save_media_batch

  from services.video_service import merge_audio as merge_audio_service

  logger.info(f"Adding BGM to video: {video_gcs_uri}")

  if bucket_name is None:
    bucket_name = GCS_BUCKET_NAME

  with tempfile.TemporaryDirectory() as temp_dir:
    # 1. Download Video
    local_video_path = os.path.join(temp_dir, "input_video.mp4")
    logger.info(f"Downloading {video_gcs_uri} to {local_video_path}")
    download_blob_to_file(video_gcs_uri, local_video_path)

    # 2. Generate BGM
    try:
      local_audio_path = await generate_bgm_music(
        video_gcs_uri=video_gcs_uri,
        prompt=prompt,
        local_dir=temp_dir,
      )
      logger.info(f"Generated BGM at {local_audio_path}")
    except Exception as e:
      logger.error(f"Failed to generate bgm: {e}")
      raise ValueError(f"Failed to generate bgm: {e}") from e

    # 3. Merge Audio
    output_filename = f"video_with_bgm_{int(time.time())}.mp4"
    local_output_path = os.path.join(temp_dir, output_filename)

    try:
      duration_seconds = merge_audio_service(
        video_path=local_video_path,
        audio_path=local_audio_path,
        output_path=local_output_path,
      )
      logger.info(f"Merged video and audio to {local_output_path}")
    except Exception as e:
      logger.error(f"Failed to merge audio: {e}")
      raise ValueError(f"Failed to merge audio: {e}") from e

    # 4. Upload Result
    try:
      with open(local_output_path, "rb") as f:
        video_bytes = f.read()

      output_gcs_uri = f"gs://{bucket_name}/videos_with_bgm"
      uploaded_uris = save_media_batch(
        media_items=[RawMediaItem(data=video_bytes, mime_type="video/mp4")],
        output_gcs_uri=output_gcs_uri,
        file_prefix="video_with_bgm",
      )
      uploaded_uri = uploaded_uris[0]
      logger.info(f"Uploaded video with BGM to {uploaded_uri}")
    except Exception as e:
      logger.error(f"Failed to upload video: {e}")
      raise ValueError(f"Failed to upload video: {e}") from e

  return VideoMetadata(uploaded_uri, duration_seconds=duration_seconds)
