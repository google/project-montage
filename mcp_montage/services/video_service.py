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
from schemas import Narrative, NarrativeLine, VideoMetadata
from schemas.media import RawMediaItem
from utils import log
from utils.ffmpeg import FfmpegRunner
from utils.image import convert_image_to_part
from utils.storage import (
  download_blob_to_file,
  download_bytes_from_gcs,
  save_media_batch,
)

from services.agents.factory import AgentFactory
from services.agents.text_agent import GeminiAgent
from services.speech_service import (
  _clean_ass_dialogue_text,
  generate_voice_profile,
)

logger = log.get_logger()

ffmpeg = FfmpegRunner()
_FONTS_DIR = os.path.join(
  os.path.dirname(os.path.dirname(__file__)),
  "assets",
  "fonts",
  "consolidated",
)

_TRANSITION_DURATION = 1.0


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
  output_gcs_uri: str,
  prompt: str | None = None,
  duration_seconds: int = 6,
  aspect_ratio: str = "16:9",
  domain_constraints: str = "",
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

  if domain_constraints:
    contents.append(f"Constraints: {domain_constraints}")

  video_prompt_builder_agent: GeminiAgent = AgentFactory.create_text_agent(agent_name="video_prompt_builder")
  resp: dict[str, str] = await video_prompt_builder_agent.generate_json_content_async(contents=contents)

  video_prompt: str = str(resp.get("video_prompt", "")).strip()

  logger.info(f"Generated video prompt: {video_prompt}")

  if domain_constraints:
    video_prompt = video_prompt + "\n\n" + domain_constraints

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
    output_gcs_uri=output_gcs_uri,
    image_uri=gcs_uri,
  )
  uploaded_uri = uploaded_uris[0]
  logger.info(f"Video generation completed. Output saved to {uploaded_uri}")

  return VideoMetadata(uploaded_uri, duration_seconds=duration_seconds)


def _extract_readable_narrative_lines(ass_content: str) -> list[NarrativeLine]:
  """Extracts readable timestamp/text pairs from ASS dialogue lines."""
  readable_lines: list[NarrativeLine] = []

  for line in ass_content.splitlines():
    if not line.startswith("Dialogue:"):
      continue

    parts = line.split(",", 9)
    if len(parts) <= 9:
      continue

    text = _clean_ass_dialogue_text(parts[9].strip())
    if not text:
      continue

    readable_lines.append(
      NarrativeLine(
        timestamp=parts[1].strip(),
        text=text,
      )
    )

  if not readable_lines:
    raise ValueError("No dialogue lines found in ASS content.")

  return readable_lines


def _count_ass_dialogue_lines(ass_content: str) -> int:
  """Counts Dialogue lines under [Events] for romanization validation."""
  return sum(1 for line in ass_content.splitlines() if line.startswith("Dialogue:"))


async def generate_narrative(
  video_gcs_uri: str,
  prompt: str | None = None,
  storyboard: str | None = None,
  domain_constraints: str = "",
) -> Narrative:
  """Generate a narration script for a video in ASS and readable formats."""
  logger.info(f"Generating narration for video: {video_gcs_uri}")

  # Use Gemini to generate ASS content
  agent = AgentFactory.create_text_agent(
    agent_name="narrative_writer",
  )

  contents: types.ContentUnionDict = [
    "Video:",
    convert_image_to_part(image=video_gcs_uri, mime_type="video/mp4"),
  ]

  if storyboard:
    contents.append(f"Storyboard: {storyboard}")

  if prompt:
    contents.append(f"Prompt: {prompt}")

  if domain_constraints:
    contents.append(f"Constraints: {domain_constraints}")

  response = await agent.generate_json_content_async(contents)
  ass_content = str(response.get("ass_content", "")).strip()
  romanization = [str(entry) for entry in response.get("romanization", [])]

  readable_content = _extract_readable_narrative_lines(ass_content)
  dialogue_count = _count_ass_dialogue_lines(ass_content)
  if len(romanization) != dialogue_count:
    raise ValueError(f"narrative_writer returned {len(romanization)} romanization entries for {dialogue_count} Dialogue lines; they must match 1:1.")
  logger.info("Generated ASS content with romanization.")

  # Cast the voice here, where the storyboard and user prompt give richer
  # context than the bare ASS the voiceover step would otherwise see. The
  # romanized transcript rides along so the pace heuristic can budget on it.
  voice_context_parts = [part for part in (storyboard, prompt) if part]
  voice_context_parts.append("Romanized transcript (for pacing):\n" + "\n".join(romanization))
  voice_profile = await generate_voice_profile(
    ass_content,
    context="\n\n".join(voice_context_parts),
  )
  logger.info(f"Selected voice profile: {voice_profile}")

  return Narrative(
    ass_content=ass_content,
    readable_content=readable_content,
    romanization=romanization,
    voice_profile=voice_profile,
  )


async def render_final_video_service(
  video_gcs_uri: str,
  bucket_name: str,
  bgm_gcs_uri: str | None = None,
  voiceover_gcs_uri: str | None = None,
  ass_content: str | None = None,
  audio_ducking: bool = True,
) -> VideoMetadata:
  """Render a finished video by muxing optional BGM, voiceover, and subtitles.

  The base video is downloaded once and each requested layer is applied in
  order on the local file: BGM (looped to length, replaces ambient audio),
  voiceover (mixed on top of whatever audio is now present), subtitle
  burn-in. Loudness is normalized at the end and the result is uploaded
  to gs://{bucket}/final_videos/.

  At least one of `bgm_gcs_uri`, `voiceover_gcs_uri`, or `ass_content` should
  be provided -- otherwise the function re-encodes the input video without
  changes.

  Args:
      video_gcs_uri: GCS URI of the base video.
      bucket_name: GCS bucket the final video is uploaded to.
      bgm_gcs_uri: Optional BGM track (from generate_bgm_service).
      voiceover_gcs_uri: Optional voiceover track
          (from generate_voiceover_service).
      ass_content: Optional raw ASS subtitle content to burn in.
      audio_ducking: Whether to duck existing audio under voiceover.

  Returns:
      VideoMetadata for the rendered video in gs://{bucket}/final_videos/.
  """
  logger.info(
    f"Composing final video for {video_gcs_uri} (bgm={bool(bgm_gcs_uri)}, vo={bool(voiceover_gcs_uri)}, subs={bool(ass_content)}, ducking={audio_ducking})."  # noqa: E501
  )

  with tempfile.TemporaryDirectory() as temp_dir:
    local_video_path = os.path.join(temp_dir, "input_video.mp4")
    download_blob_to_file(video_gcs_uri, local_video_path)

    current_path = local_video_path
    step = 0

    if bgm_gcs_uri:
      local_bgm_path = os.path.join(temp_dir, "bgm.wav")
      download_blob_to_file(bgm_gcs_uri, local_bgm_path)

      next_path = os.path.join(temp_dir, f"step{step}_with_bgm.mp4")
      step += 1
      merge_audio(
        video_path=current_path,
        audio_path=local_bgm_path,
        output_path=next_path,
      )
      current_path = next_path

    if voiceover_gcs_uri:
      local_vo_path = os.path.join(temp_dir, "voiceover.wav")
      download_blob_to_file(voiceover_gcs_uri, local_vo_path)

      next_path = os.path.join(temp_dir, f"step{step}_with_vo.mp4")
      step += 1
      ffmpeg.mix_vo_with_video_audio(
        video_path=current_path,
        vo_path=local_vo_path,
        output_path=next_path,
        audio_ducking=audio_ducking,
      )
      current_path = next_path

    if ass_content:
      local_ass_path = os.path.join(temp_dir, "subtitles.ass")
      with open(local_ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

      next_path = os.path.join(temp_dir, f"step{step}_with_subs.mp4")
      step += 1
      ffmpeg.burn_in_subtitles(
        input_video_path=current_path,
        subtitle_path=local_ass_path,
        output_path=next_path,
        fonts_dir=_FONTS_DIR,
      )
      current_path = next_path

    normalized_path = ffmpeg.normalize_loudness(current_path)

    with open(normalized_path, "rb") as f:
      video_bytes = f.read()

    uploaded_uris = save_media_batch(
      media_items=[RawMediaItem(data=video_bytes, mime_type="video/mp4")],
      output_gcs_uri=f"gs://{bucket_name}/final_videos",
      file_prefix="final_video",
    )
    uploaded_uri = uploaded_uris[0]

    duration_seconds = ffmpeg.get_video_duration(normalized_path)

  logger.info(f"Final video uploaded: {uploaded_uri}")
  return VideoMetadata(
    gcs_uri=uploaded_uri,
    duration_seconds=duration_seconds,
  )
