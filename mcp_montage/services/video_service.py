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

import os
import tempfile
import time

from google.genai import types
from schemas import FileMetadata, GenerateSceneNarrativesResponse, VideoMetadata
from schemas.media import RawMediaItem
from shared.constants import GCS_BUCKET_NAME
from utils import log
from utils.ffmpeg import FfmpegRunner
from utils.image import convert_image_to_part
from utils.storage import (
  download_blob_to_file,
  download_bytes_from_gcs,
  save_media_batch,
)

from services.agents.config.prompt_loader import (  # noqa: E501
  video_constraints_prompt,
)
from services.agents.factory import AgentFactory
from services.agents.text_agent import GeminiAgent

logger = log.get_logger()

_TRANSITION_DURATION = 1.0
ffmpeg = FfmpegRunner()
_OPEN_SANS_DIR = os.path.join(
  os.path.dirname(os.path.dirname(__file__)),
  "assets",
  "fonts",
  "Open_Sans",
  "static",
)
_OPEN_SANS_FORCE_STYLE = "Fontname=Open Sans"


def concatenate_videos_with_transition(
  video_gcs_uris: list[str],
  output_gcs_uri: str,
  transition: str = "fade",
) -> VideoMetadata:
  """
  Concatenate video clips together with specified transition effects.
  """
  with tempfile.TemporaryDirectory() as temp_dir:
    local_video_paths = []
    for i, uri in enumerate(video_gcs_uris):
      local_path = os.path.join(temp_dir, f"video_{i}.mp4")
      logger.info(f"Downloading {uri} to {local_path}")
      download_blob_to_file(uri, local_path)
      local_video_paths.append(local_path)

    # Iteratively apply transitions
    if not local_video_paths:
      logger.error("No videos to concatenate")
      raise ValueError("No videos to concatenate")

    current_video_path = local_video_paths[0]
    output_filename = f"concatenated_{int(time.time())}.mp4"

    for i, next_video_path in enumerate(local_video_paths[1:]):
      temp_output_path = os.path.join(temp_dir, f"transition_{i}.mp4")
      current_duration = ffmpeg.get_video_duration(current_video_path)
      offset = max(0, current_duration - _TRANSITION_DURATION)

      ffmpeg.apply_transition(
        input_path1=current_video_path,
        input_path2=next_video_path,
        output_path=temp_output_path,
        transition=transition,
        duration=_TRANSITION_DURATION,
        offset=offset,
      )
      current_video_path = temp_output_path

    # Apply fade out to the concatenated video
    final_output_path = os.path.join(temp_dir, f"faded_{output_filename}")
    ffmpeg.apply_fade_out(current_video_path, final_output_path)

    with open(final_output_path, "rb") as f:
      video_bytes = f.read()

    uploaded_uris = save_media_batch(
      media_items=[RawMediaItem(data=video_bytes, mime_type="video/mp4")],
      output_gcs_uri=output_gcs_uri,
      file_prefix="concatenated",
    )
    uploaded_uri = uploaded_uris[0]
    logger.info(f"Uploading concatenated video to {uploaded_uri}")

    # Get duration of the final video
    duration = ffmpeg.get_video_duration(final_output_path)

    return VideoMetadata(uploaded_uri, duration_seconds=duration)


def concatenate_videos(
  video_gcs_uris: list[str],
  output_gcs_uri: str,
) -> VideoMetadata:
  """
  Concatenate video clips together without transitions using ffmpeg concat demuxer.
  """  # noqa: E501
  with tempfile.TemporaryDirectory() as temp_dir:
    local_video_paths = []
    for i, uri in enumerate(video_gcs_uris):
      local_path = os.path.join(temp_dir, f"video_{i}.mp4")
      logger.info(f"Downloading {uri} to {local_path}")
      download_blob_to_file(uri, local_path)
      local_video_paths.append(local_path)

    output_filename = f"concatenated_{int(time.time())}.mp4"
    local_output_path = os.path.join(temp_dir, output_filename)

    # Create a file list for ffmpeg
    list_file_path = os.path.join(temp_dir, "filelist.txt")
    with open(list_file_path, "w") as f:
      for path in local_video_paths:
        # Escape single quotes for ffmpeg concat demuxer
        safe_path = path.replace("'", "'\\''")
        f.write(f"file '{safe_path}'\n")

    ffmpeg.concat_videos_from_listfile(list_file_path, local_output_path)

    # Apply fade out to the concatenated video
    final_output_path = os.path.join(temp_dir, f"faded_{output_filename}")
    ffmpeg.apply_fade_out(local_output_path, final_output_path)

    with open(final_output_path, "rb") as f:
      video_bytes = f.read()
    uploaded_uris = save_media_batch(
      media_items=[RawMediaItem(data=video_bytes, mime_type="video/mp4")],
      output_gcs_uri=output_gcs_uri,
      file_prefix="concatenated",
    )
    uploaded_uri = uploaded_uris[0]
    logger.info(f"Uploading concatenated video to {uploaded_uri}")

    # Get duration of the final video
    duration = ffmpeg.get_video_duration(final_output_path)

    return VideoMetadata(gcs_uri=uploaded_uri, duration_seconds=duration)


def merge_audio(
  video_path: str,
  audio_path: str,
  output_path: str,
) -> float:
  """
  Merges video and audio with fade effects using FFMPEG.
  Video duration determines the length. Audio fades in at start and out at end.
  Refactored from generate_bgm_and_merge.
  """  # noqa: E501
  # Check if audio is shorter than video and loop if necessary
  video_duration = ffmpeg.get_video_duration(video_path)
  audio_duration = ffmpeg.get_video_duration(audio_path)

  # Check if audio is shorter than video and loop if necessary
  # Use a temporary directory for the looped audio file
  with tempfile.TemporaryDirectory() as temp_dir:
    final_audio_path = audio_path
    if audio_duration < video_duration:
      logger.info(
        f"Audio duration ({audio_duration}s) is shorter than video ({video_duration}s). Looping audio.",  # noqa: E501
      )
      name, ext = os.path.splitext(os.path.basename(audio_path))
      looped_audio_path = os.path.join(temp_dir, f"{name}_looped{ext}")
      ffmpeg.loop_audio(audio_path, looped_audio_path, video_duration)
      final_audio_path = looped_audio_path

    return ffmpeg.merge_audio(
      video_path=video_path,
      audio_path=final_audio_path,
      output_path=output_path,
    )


async def generate_video_service(
  gcs_uri: str,
  prompt: str | None = None,
  duration_seconds: int = 6,
  aspect_ratio: str = "16:9",
  output_dir: str = "tests",
) -> VideoMetadata:
  """Generate a video from an image using Veo model."""

  logger.info(f"Queueing video generation for: {gcs_uri}")

  # Step 1: Use Gemini to generate a prompt for video generation
  contents: types.ContentUnionDict = [
    "Image:",
    convert_image_to_part(
      image=gcs_uri,
      mime_type="image/png",
    ),
  ]

  if prompt:
    contents.append(f"Text prompt: {prompt}")

  video_prompt_builder_agent: GeminiAgent = AgentFactory.create_text_agent(
    agent_name="video_prompt_builder"
  )
  resp: dict[
    str, str
  ] = await video_prompt_builder_agent.generate_json_content_async(
    contents=contents
  )
  video_prompt_builder_agent: GeminiAgent = AgentFactory.create_text_agent(
    agent_name="video_prompt_builder"
  )
  resp: dict[
    str, str
  ] = await video_prompt_builder_agent.generate_json_content_async(
    contents=contents
  )

  video_prompt: str = str(resp.get("video_prompt", "")).strip()

  logger.info(f"Generated video prompt: {video_prompt}")

  video_prompt = video_prompt + "\n\n" + video_constraints_prompt

  # Step 2: Veo agent to generate a video from the image
  video_agent = AgentFactory.create_video_agent()

  uploaded_uris = await video_agent.image_to_videos(
    prompt=video_prompt,
    first_frame_bytes=download_bytes_from_gcs(gcs_uri),
    aspect_ratio=aspect_ratio,
    output_dir=output_dir,
    number_of_videos=1,
    duration_seconds=duration_seconds,
    negative_prompt="Speaking, Character's voice",
    output_gcs_uri=f"gs://{GCS_BUCKET_NAME}/generated_videos",
  )
  uploaded_uri = uploaded_uris[0]
  logger.info(f"Video generation completed. Output saved to {uploaded_uri}")

  return VideoMetadata(uploaded_uri, duration_seconds=duration_seconds)


async def generate_scene_narratives(
  video_gcs_uri: str,
  prompt: str | None = None,
) -> GenerateSceneNarrativesResponse:
  """Generate a narration script for a video."""
  logger.info(f"Generating narration for video: {video_gcs_uri}")

  # Use Gemini to generate ASS content
  agent = AgentFactory.create_text_agent(
    agent_name="narrative_writer",
  )

  contents: types.ContentUnionDict = [
    "Video:",
    convert_image_to_part(image=video_gcs_uri, mime_type="video/mp4"),
  ]

  if prompt:
    contents.append(f"Prompt: {prompt}")

  response_text = await agent.generate_content_async(contents)
  ass_content = response_text.strip()

  # Clean up markdown code blocks if present
  if ass_content.startswith("```"):
    # Remove first line (```srt or just ```) and last line (```)
    lines = ass_content.split("\n")
    if len(lines) >= 2:
      ass_content = "\n".join(lines[1:-1]).strip()

  logger.info("Generated ASS content.")

  with tempfile.TemporaryDirectory() as temp_dir:
    # Save ASS locally for ffmpeg embedding
    local_ass_path = os.path.join(temp_dir, "narrative.ass")
    with open(local_ass_path, "w", encoding="utf-8") as f:
      f.write(ass_content)

    # Download video locally
    local_video_path = os.path.join(temp_dir, "input_video.mp4")
    download_blob_to_file(video_gcs_uri, local_video_path)

    # Embed subtitles using ffmpeg (burn-in)
    output_filename = f"subtitled_{int(time.time())}.mp4"
    local_output_path = os.path.join(temp_dir, output_filename)
    ffmpeg.burn_in_subtitles(
      input_video_path=local_video_path,
      subtitle_path=local_ass_path,
      output_path=local_output_path,
      fonts_dir=_OPEN_SANS_DIR,
      force_style=_OPEN_SANS_FORCE_STYLE,
    )

    # Upload ASS to GCS
    ass_uploaded_uris = save_media_batch(
      media_items=[
        RawMediaItem(
          data=ass_content.encode("utf-8"), mime_type="application/x-ass"
        )
      ],
      output_gcs_uri=f"gs://{GCS_BUCKET_NAME}/narratives",
      file_prefix="narrative",
    )
    ass_uploaded_uri = ass_uploaded_uris[0]

    # Upload subtitled video to GCS
    with open(local_output_path, "rb") as f:
      video_bytes = f.read()

    video_uploaded_uris = save_media_batch(
      media_items=[RawMediaItem(data=video_bytes, mime_type="video/mp4")],
      output_gcs_uri=f"gs://{GCS_BUCKET_NAME}/videos_with_subtitles",
      file_prefix="video_with_subtitles",
    )
    video_uploaded_uri = video_uploaded_uris[0]

    duration_seconds = ffmpeg.get_video_duration(local_output_path)

  logger.info(f"Narrative generation completed: {ass_uploaded_uri}")
  logger.info(f"Subtitled video uploaded: {video_uploaded_uri}")

  return GenerateSceneNarrativesResponse(
    srt_file=FileMetadata(gcs_uri=ass_uploaded_uri),
    video=VideoMetadata(
      gcs_uri=video_uploaded_uri, duration_seconds=duration_seconds
    ),
  )
