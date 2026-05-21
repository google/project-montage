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

import json
import math
import os
import subprocess

from utils import log

logger = log.get_logger()


def _escape_subtitles_path(path: str) -> str:
  """
  Escape subtitle paths for ffmpeg's subtitles filter across OSes.
  Windows requires POSIX-style paths and escaped drive colon.
  Unix-like shells should keep the native absolute path.
  """
  abs_path = os.path.abspath(path)
  if os.name == "nt":
    posix_path = abs_path.replace("\\", "/")
    posix_path = posix_path.replace(":", "\\:")
    posix_path = posix_path.replace("'", "\\'")
    return posix_path
  return abs_path.replace("'", "\\'")


def _escape_filter_value(value: str) -> str:
  return value.replace("'", "\\'")


class FfmpegFilters:
  """Pure helpers for building ffmpeg filter strings."""

  @staticmethod
  def xfade(transition: str, duration: float, offset: float) -> str:
    return f"[0:v][1:v]xfade=transition={transition}:duration={duration}:offset={offset}[v]"  # noqa: E501

  @staticmethod
  def fade_out(start_time: float, duration: float) -> tuple[str, str]:
    return (
      f"fade=t=out:st={start_time}:d={duration}",
      f"afade=t=out:st={start_time}:d={duration}",
    )

  @staticmethod
  def audio_fade(duration: float, fade_duration: float = 1.0) -> str:
    fade_out_start = max(0, duration - fade_duration)
    return f"[1:a]afade=t=in:st=0:d={fade_duration},afade=t=out:st={fade_out_start}:d={fade_duration}[a]"  # noqa: E501

  @staticmethod
  def subtitles_burn_in(
    subtitle_path: str,
    fonts_dir: str | None = None,
    force_style: str | None = None,
  ) -> str:
    safe_path = _escape_subtitles_path(subtitle_path)
    options = [f"filename='{safe_path}'"]
    if fonts_dir:
      safe_fonts_dir = _escape_subtitles_path(fonts_dir)
      options.append(f"fontsdir='{safe_fonts_dir}'")
    if force_style:
      safe_force_style = _escape_filter_value(force_style)
      options.append(f"force_style='{safe_force_style}'")
    return "subtitles=" + ":".join(options)


class FfmpegRunner:
  """Lightweight wrapper for executing ffmpeg/ffprobe commands."""

  def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe"):
    self._ffmpeg_bin = ffmpeg_bin
    self._ffprobe_bin = ffprobe_bin

  def _run(self, args: list[str], label: str) -> None:
    cmd = [self._ffmpeg_bin, *args]
    logger.info(f"Running ffmpeg {label} command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, capture_output=True)

  def _probe(self, args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [self._ffprobe_bin, *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=True)

  def get_video_duration(self, input_path: str) -> float:
    """
    Gets the duration of a video file using ffprobe.
    """
    result = self._probe(
      [
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        input_path,
      ]
    )
    return float(result.stdout)

  def apply_transition(
    self,
    input_path1: str,
    input_path2: str,
    output_path: str,
    transition: str = "fade",
    duration: float = 1.0,
    offset: float = 0.0,
  ) -> None:
    filter_complex = FfmpegFilters.xfade(transition, duration, offset)
    self._run(
      [
        "-i",
        input_path1,
        "-i",
        input_path2,
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-y",
        output_path,
      ],
      label="transition",
    )

  def apply_fade_out(
    self, input_path: str, output_path: str, duration: float = 1.0
  ) -> None:
    video_duration = self.get_video_duration(input_path)
    start_time = max(0, video_duration - duration)
    video_filter, audio_filter = FfmpegFilters.fade_out(start_time, duration)
    self._run(
      [
        "-i",
        input_path,
        "-vf",
        video_filter,
        "-af",
        audio_filter,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-y",
        output_path,
      ],
      label="fade-out",
    )

  def merge_audio(
    self,
    video_path: str,
    audio_path: str,
    output_path: str,
  ) -> float:
    """
    Merges video and audio with fade effects using FFMPEG.
    Video duration determines the length. Audio fades in at start and out at end.
    Refactored from generate_bgm_and_merge.
    """  # noqa: E501
    if not os.path.exists(audio_path):
      logger.warning(f"Audio file not found at {audio_path}, skipping merge.")
      pass

    try:
      duration = self.get_video_duration(video_path)
    except (subprocess.CalledProcessError, ValueError) as e:
      logger.error(f"Failed to get video duration: {e}")
      raise ValueError(f"Failed to get video duration: {e}") from e

    filter_complex = FfmpegFilters.audio_fade(duration)
    logger.info(f"Using audio filter: {filter_complex}")

    try:
      self._run(
        [
          "-i",
          video_path,
          "-i",
          audio_path,
          "-filter_complex",
          filter_complex,
          "-map",
          "0:v",
          "-map",
          "[a]",
          "-c:v",
          "copy",
          "-c:a",
          "aac",
          "-shortest",
          "-y",
          output_path,
        ],
        label="merge-audio",
      )
      return duration
    except subprocess.CalledProcessError as e:
      logger.error(f"FFmpeg merge failed: {e}")
      raise ValueError(f"FFmpeg merge failed: {e}") from e

  def concat_videos_from_listfile(
    self, list_file_path: str, output_path: str
  ) -> None:
    """
    Concatenate videos using ffmpeg concat demuxer.
    """
    self._run(
      [
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file_path,
        "-c:v",
        "copy",
        "-y",
        output_path,
      ],
      label="concat",
    )

  def embed_subtitles(
    self,
    input_video_path: str,
    subtitle_path: str,
    output_path: str,
  ) -> None:
    """
    Embed subtitles into a video as a soft subtitle track.
    """
    self._run(
      [
        "-i",
        input_video_path,
        "-i",
        subtitle_path,
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-c:s",
        "mov_text",
        "-map",
        "0",
        "-map",
        "1",
        "-y",
        output_path,
      ],
      label="subtitles",
    )

  def burn_in_subtitles(
    self,
    input_video_path: str,
    subtitle_path: str,
    output_path: str,
    fonts_dir: str | None = None,
    force_style: str | None = None,
  ) -> None:
    """
    Burn in subtitles into the video using the subtitles filter.
    """
    subtitles_filter = FfmpegFilters.subtitles_burn_in(
      subtitle_path,
      fonts_dir=fonts_dir,
      force_style=force_style,
    )
    self._run(
      [
        "-i",
        input_video_path,
        "-vf",
        subtitles_filter,
        "-y",
        output_path,
      ],
      label="burn-in-subtitles",
    )

  def normalize_loudness(
    self,
    input_file: str,
    target_i: float = -23.0,
    target_lra: float = 7.0,
    target_tp: float = -2.0,
    sample_rate: int = 48000,
    audio_bitrate: str = "500k",
    audio_channels: int = 6,
  ) -> str:
    """
    Normalizes video audio loudness using a two-pass FFmpeg method.

    First pass measures loudness stats, second pass applies precise normalization.
    """  # noqa: E501
    file_extension = os.path.splitext(input_file)[1]
    output_file = input_file.replace(
      file_extension, f"_normalized{file_extension}"
    )

    # 1. First Pass: Analyze the audio to get loudness stats
    analysis_cmd = [
      "-i",
      input_file,
      "-filter:a",
      "loudnorm=print_format=json",
      "-f",
      "null",
      "-",
    ]

    try:
      # We use subprocess directly here to capture stderr specifically
      cmd = [self._ffmpeg_bin, *analysis_cmd]
      logger.info(f"Running ffmpeg loudness analysis: {' '.join(cmd)}")
      result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, ValueError) as e:
      logger.error(f"Loudness Analysis Error: {e}")
      return input_file

    # Extract the JSON block from the stderr output
    try:
      # Find the last occurrence of '{' in stderr where ffmpeg prints JSON
      stats_str = result.stderr[result.stderr.rfind("{") :]
      stats_str = stats_str.split("}")[0] + "}"
      stats = json.loads(stats_str)
    except (ValueError, json.JSONDecodeError, KeyError) as e:
      logger.error(f"Error parsing ffmpeg loudness output: {e}")
      return input_file

    # 2. Second Pass: Apply normalization using the measured stats
    filter_string = f"loudnorm=linear=true:I={target_i}:LRA={target_lra}:tp={target_tp}:measured_I={stats['input_i']}:measured_LRA={stats['input_lra']}:measured_tp={stats['input_tp']}:measured_thresh={stats['input_thresh']}:offset={stats['target_offset']},aresample=resampler=soxr:out_sample_rate={sample_rate}:precision=28"  # noqa: E501

    _, input_ext = os.path.splitext(input_file.lower())
    _, output_ext = os.path.splitext(output_file.lower())

    is_input_wav = input_ext == ".wav"
    is_output_wav = output_ext == ".wav"

    cmd_args = ["-y", "-i", input_file, "-filter:a", filter_string]

    if is_output_wav:
      cmd_args.extend(["-c:a", "pcm_s16le"])
    else:
      if not is_input_wav:
        cmd_args.extend(["-c:v", "copy"])
      cmd_args.extend(["-c:a", "aac", "-b:a", audio_bitrate])

    cmd_args.extend(["-ac", str(audio_channels), output_file])

    try:
      self._run(cmd_args, label="normalize-loudness")
    except Exception as e:
      logger.error(f"Loudness Normalization Error: {e}")
      return input_file

    return output_file

  def loop_audio(
    self,
    input_path: str,
    output_path: str,
    duration: float,
    fade_duration: float = 0.5,
  ) -> None:
    """
    Loops the audio file with a crossfade between loops to match duration.
    """
    try:
      input_dur = self.get_video_duration(input_path)
    except Exception:
      input_dur = 0

    if input_dur <= 0 or input_dur >= duration:
      self._run(
        ["-i", input_path, "-t", str(duration), "-y", output_path],
        label="trim-audio",
      )
      return

    # Ensure fade_duration is reasonable
    fade_duration = min(fade_duration, input_dur / 2)

    # Calculate number of loops needed.
    # Total duration approx = N * (input_dur - fade_duration) + fade_duration
    num_loops = math.ceil(
      (duration - fade_duration) / (input_dur - fade_duration)
    )

    # Standard aloop if loops are too many or fade is zero
    if num_loops > 20 or fade_duration <= 0:
      self._run(
        [
          "-i",
          input_path,
          "-filter_complex",
          "aloop=loop=-1:size=2e+09",
          "-t",
          str(duration),
          "-y",
          output_path,
        ],
        label="loop-audio-legacy",
      )
      return

    inputs = []
    filters = []
    for _ in range(num_loops):
      inputs.extend(["-i", input_path])

    prev_label = "0:a"
    for i in range(1, num_loops):
      next_label = f"a{i}"
      filters.append(
        f"[{prev_label}][{i}:a]acrossfade=d={fade_duration}:c1=tri:c2=tri[{next_label}]"
      )
      prev_label = next_label

    self._run(
      [
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{prev_label}]",
        "-t",
        str(duration),
        "-y",
        output_path,
      ],
      label="loop-audio-fade",
    )
