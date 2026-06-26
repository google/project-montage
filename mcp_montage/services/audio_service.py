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

from google.genai import types
from schemas import AudioMetadata
from schemas.media import RawMediaItem
from utils import log
from utils.ffmpeg import FfmpegRunner
from utils.image import convert_image_to_part
from utils.storage import save_media_batch

from services import lyria_service
from services.agents.factory import AgentFactory

logger = log.get_logger()


async def generate_bgm_music(
  video_gcs_uri: str,
  prompt: str | None = None,
  local_dir: str | None = None,
  domain_constraints: str = "",
) -> str:
  """Generates BGM music using the Lyria API.

  Args:
      video_gcs_uri: GCS URI of the video to generate BGM for.
      prompt: (Optional) Additional prompt for the music.
      local_dir: (Optional) Local directory to save the generated music.
      domain_constraints: (Optional) Domain-specific rules appended to the
          music prompt builder input.

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

  if domain_constraints:
    user_prompt_parts.append(domain_constraints)

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


async def generate_bgm_service(
  video_gcs_uri: str,
  bucket_name: str,
  prompt: str | None = None,
  domain_constraints: str = "",
) -> AudioMetadata:
  """Generates background music for a video and uploads it to GCS.

  This is a generation-only step; muxing into a video is the responsibility
  of `services.video_service.render_final_video_service`.

  Args:
      video_gcs_uri: GCS URI of the video used as scoring reference.
      bucket_name: GCS bucket the resulting BGM track is uploaded to.
      prompt: Optional text guidance for the music prompt builder.
      domain_constraints: (Optional) Domain-specific rules appended to the
          music prompt builder input.

  Returns:
      AudioMetadata for the uploaded WAV track in gs://{bucket}/bgm/.
  """
  import tempfile

  logger.info(f"Generating BGM for video: {video_gcs_uri}")

  with tempfile.TemporaryDirectory() as temp_dir:
    try:
      local_audio_path = await generate_bgm_music(
        video_gcs_uri=video_gcs_uri,
        prompt=prompt,
        local_dir=temp_dir,
        domain_constraints=domain_constraints,
      )
      logger.info(f"Generated BGM at {local_audio_path}")
    except Exception as e:
      logger.error(f"Failed to generate bgm: {e}")
      raise ValueError(f"Failed to generate bgm: {e}") from e

    ffmpeg = FfmpegRunner()
    duration_seconds = ffmpeg.get_video_duration(local_audio_path)

    with open(local_audio_path, "rb") as f:
      audio_bytes = f.read()

    uploaded_uris = save_media_batch(
      media_items=[RawMediaItem(data=audio_bytes, mime_type="audio/wav")],
      output_gcs_uri=f"gs://{bucket_name}/bgm",
      file_prefix="bgm",
    )
    uploaded_uri = uploaded_uris[0]
    logger.info(f"Uploaded BGM to {uploaded_uri}")

  return AudioMetadata(
    gcs_uri=uploaded_uri,
    duration_seconds=duration_seconds,
  )
