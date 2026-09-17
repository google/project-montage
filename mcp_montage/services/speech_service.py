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

"""Speech generation, alignment, and voiceover-stitching helpers."""

import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

import torch
import torchaudio
from schemas import AudioMetadata, VoiceProfile
from torchaudio.pipelines import MMS_FA as bundle
from utils import log
from utils.ffmpeg import FfmpegRunner
from utils.storage import upload_file_to_gcs

from services.agents.factory import AgentFactory
from services.agents.prompts.voice_profile_picker import (
  DEFAULT_VOICE_NAME,
  VOICE_CONFIG,
)

logger = log.get_logger()

ffmpeg = FfmpegRunner()

# Maximum number of refinement turns we'll ask the narrative_refiner agent
# for. One additional initial voiceover generation happens before the first
# retry, so the worst case is MAX_VOICEOVER_REFINEMENT_RETRIES + 1 TTS calls.
MAX_VOICEOVER_REFINEMENT_RETRIES: int = 5

# Chunks whose generated audio runs past their ASS window by less than this
# much (whichever is larger) are accepted without invoking the refinement
# loop -- the existing `max(chunk.end_time, ...)` padding swallows them.
_OVERRUN_TOLERANCE_RELATIVE: float = 0.05
_OVERRUN_TOLERANCE_ABSOLUTE: float = 0.15

# Words whose forced-alignment confidence (probability in [0, 1]) falls below
# this are treated as "weak" -- likely not actually spoken. A run of at least
# `_MIN_DROPPED_RUN` consecutive weak words is treated as a dropped phrase.
_DROP_SCORE_THRESHOLD: float = 0.20
_MIN_DROPPED_RUN: int = 2

# Maximum number of seed-varied full regenerations attempted when a phrase is
# dropped. The script is unchanged across these; only the TTS seed varies.
MAX_VOICEOVER_REGENERATION_RETRIES: int = 3

# Bounds on how far `_align_subtitle_chunks_to_words` will search ahead of a
# chunk's own expected position for a token match. Without a bound, a single
# word the TTS dropped (or reworded past what the tolerant matchers above
# recognize) lets the scan keep advancing token-by-token -- and the partial-
# match reverse scan keep searching backward from the very end of the whole
# transcript -- until it finds *some* coincidental match, however far away.
# That lets one chunk's segment swallow audio belonging to a later scene,
# and strands the scenes in between with no reachable tokens of their own.
# The window is sized relative to the chunk's own token count so normal
# insertions/skips are still tolerated; it just stops the search before it
# can wander into a different scene's dialogue.
_ALIGNMENT_SEARCH_WINDOW_MULTIPLE: int = 4
_ALIGNMENT_SEARCH_MIN_WINDOW: int = 10

# Lazy load forced-alignment model to avoid delay on startup.
_device = None
_model = None
_tokenizer = None
_aligner = None


AUDIO_PROFILES: dict[str, str] = {
  "warm_premium_commercial": (
    "A smooth, premium commercial voice -- polished and inviting."
  ),
  "energetic_promo": ("A high-energy hype voice that lands every consonant."),
  "professional_newscaster": ("A clear, authoritative broadcast voice."),
  "intimate_confidant": ("A close, breathy voice that feels one-to-one."),
  "friendly_conversationalist": (
    "A warm, casual voice that talks with the listener, not at them."
  ),
  "sophisticated_luxury": ("A poised, refined voice with deliberate cadence."),
  "documentary_narrator": (
    "A grounded, observational voice with measured authority."
  ),
}

VOICE_STYLES: dict[str, str] = {
  "vocal_smile": (
    "Vocal Smile -- the soft palate is raised to keep the tone bright, sunny, and explicitly inviting."  # noqa: E501
  ),
  "newscaster": (
    "Newscaster -- professional, authoritative, clear articulation with standard broadcast cadence."  # noqa: E501
  ),
  "whisper": ("Whisper -- intimate, breathy, close-to-mic proximity effect."),  # noqa: E501
  "empathetic": (
    "Empathetic -- warm, understanding, soft tone with gentle inflections."
  ),
  "promo_hype": (
    "Promo/Hype -- high energy, punchy consonants, elongated vowels on excitement words."  # noqa: E501
  ),
  "deadpan": ("Deadpan -- flat affect, minimal pitch variation, dry delivery."),
}

PACE_OPTIONS: dict[str, str] = {
  "natural": "Natural conversational pace.",
  "rapid_fire": "Fast, energetic pace.",
  "the_drift": (
    "The Drift -- slow, liquid, zero urgency. Long pauses for breath."
  ),
}


@dataclass(slots=True)
class WordTimestamp:
  """Recognized word and its start/end timestamps in seconds."""

  word: str
  start_time: float
  end_time: float
  score: float = 1.0


@dataclass(slots=True)
class SubtitleChunk:
  """Dialogue chunk extracted from ASS with timing and word span.

  `text` is the native-script dialogue (sent to TTS and shown to users);
  `alignment_text` is its ASCII romanization, consumed exclusively by the
  forced-alignment path. For English-only input the two are identical.
  """

  text: str
  alignment_text: str
  start_time: float
  end_time: float
  start_word_index: int
  end_word_index: int


@dataclass(slots=True, frozen=True)
class ChunkOverrun:
  """One dialogue chunk whose synthesised audio overruns its ASS window."""

  index: int
  window_seconds: float
  audio_seconds: float
  over_percent: float


@dataclass(slots=True, frozen=True)
class DroppedPhrase:
  """A run of consecutive low-confidence words the TTS likely dropped."""

  start_word_index: int
  end_word_index: int
  words: tuple[str, ...]
  min_score: float
  mean_score: float


@dataclass(slots=True)
class _VoiceoverAttempt:
  """Result of one TTS + forced-alignment + segment-extraction pass."""

  subtitle_chunks: list[SubtitleChunk]
  timed_segment_paths: list[tuple[str, float, float]]
  windows_and_audio: list[tuple[float, float]]
  word_timestamps: list[WordTimestamp]


def _init_model():
  global _device, _model, _tokenizer, _aligner
  if _model is None:
    logger.info("Initializing MMS_FA forced alignment model...")
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _model = bundle.get_model().to(_device)
    _tokenizer = bundle.get_tokenizer()
    _aligner = bundle.get_aligner()
    logger.info(f"Model loaded on {_device}.")


def warm_up_forced_alignment_model() -> bool:
  """Eagerly load the MMS_FA model so the first request doesn't pay for it.

  Intended to run once at server startup. Loading the ~1.2 GB model the first
  time `generate_voiceover` is handled spikes memory mid-request; doing it at
  boot makes the footprint predictable and reuses the singleton thereafter.

  Failures (e.g. the cached weights aren't baked into the image and the
  download can't be reached) are swallowed and logged so they don't crash
  startup -- the lazy `_init_model` path retries on the first real request.

  Returns:
    True when the model is loaded, False when warm-up failed.
  """
  try:
    _init_model()
    return True
  except Exception:
    logger.warning(
      "Forced-alignment model warm-up failed; falling back to lazy load on first use.",  # noqa: E501
      exc_info=True,
    )
    return False


def normalize_text(text: str) -> str:
  text = text.lower().replace("’", "'").replace("â€™", "'")
  text = text.replace("&", " and ").replace("/", " ")
  text = re.sub("([^a-z' ])", " ", text)
  text = re.sub(" +", " ", text)
  return text.strip()


def _word_score_from_span(span) -> float:
  """Duration-weighted mean of a word's per-character alignment scores.

  Each element of `span` is a TokenSpan exposing `.score` (a probability in
  [0, 1]) and a frame length via `len()`. Weighting by frame length keeps a
  single weak phoneme inside an otherwise strong word from dragging the word's
  score below the drop threshold.

  Args:
    span: The list of per-character TokenSpans the aligner produced for one
      word.

  Returns:
    The duration-weighted mean score, or 0.0 for a fully collapsed (zero-frame)
    word so the caller never divides by zero.
  """
  total_frames = sum(len(s) for s in span)
  if total_frames <= 0:
    return 0.0
  return sum(s.score * len(s) for s in span) / total_frames


def align_audio_with_transcript(
  audio_path: str,
  transcript: str,
) -> list[WordTimestamp]:
  """Aligns audio with a known transcript and returns word timestamps."""
  _init_model()

  normalized_transcript = normalize_text(transcript)
  transcript_list = normalized_transcript.split()

  if not transcript_list:
    return []

  logger.info(
    f"Aligning audio {audio_path} with transcript of length {len(transcript_list)}"  # noqa: E501
  )

  waveform, sample_rate = torchaudio.load(audio_path)
  if sample_rate != bundle.sample_rate:
    resampler = torchaudio.transforms.Resample(
      orig_freq=sample_rate, new_freq=bundle.sample_rate
    )
    waveform = resampler(waveform)

  if waveform.size(0) > 1:
    waveform = waveform.mean(dim=0, keepdim=True)

  with torch.inference_mode():
    emission, _ = _model(waveform.to(_device))
    token_spans = _aligner(emission[0], _tokenizer(transcript_list))

  ratio = waveform.size(1) / emission.size(1) / bundle.sample_rate

  words: list[WordTimestamp] = []
  for word, span in zip(transcript_list, token_spans, strict=True):
    t0 = span[0].start * ratio
    t1 = span[-1].end * ratio
    words.append(
      WordTimestamp(
        word=word,
        start_time=t0,
        end_time=t1,
        score=_word_score_from_span(span),
      )
    )

  logger.info(f"Generated {len(words)} word timestamps via forced alignment.")
  return words


def _parse_ass_timestamp(value: str) -> float:
  """Converts an ASS timestamp like 0:00:02.80 into seconds."""
  hours, minutes, seconds = value.strip().split(":")
  return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _clean_ass_dialogue_text(text: str) -> str:
  """Removes ASS formatting and normalizes dialogue text."""
  text = re.sub(r"\{.*?\}", "", text)
  text = text.replace("\\N", " ").replace("\\n", " ").replace("\\h", " ")
  return " ".join(text.split()).strip()


def _normalize_alignment_token(token: str) -> str:
  """Normalizes tokens for tolerant subtitle/audio matching."""
  normalized = token.lower().replace("â€™", "'").replace("’", "'")
  normalized = normalized.replace("&", "and")
  return re.sub(r"[^a-z0-9]", "", normalized)


def _tokens_match(expected_token: str, actual_token: str) -> bool:
  """Returns True when two tokens are close enough for alignment."""
  expected = _normalize_alignment_token(expected_token)
  actual = _normalize_alignment_token(actual_token)

  if not expected or not actual:
    return False

  if expected == actual:
    return True

  interchangeable_groups = (
    {"and", "n"},
    {"your", "youre"},
  )
  if any(
    expected in group and actual in group for group in interchangeable_groups
  ):
    return True

  if len(expected) >= 4 and len(actual) >= 4:
    threshold = 0.7 if min(len(expected), len(actual)) >= 6 else 0.78
    return SequenceMatcher(None, expected, actual).ratio() >= threshold

  return False


def _merged_tokens_match(
  left_token: str,
  right_token: str,
  merged_token: str,
) -> bool:
  """Matches cases where ASR merges or splits adjacent words."""
  combined = _normalize_alignment_token(
    left_token
  ) + _normalize_alignment_token(right_token)
  merged = _normalize_alignment_token(merged_token)

  if not combined or not merged:
    return False

  if combined == merged:
    return True

  if len(combined) >= 4 and len(merged) >= 4:
    return SequenceMatcher(None, combined, merged).ratio() >= 0.86

  return False


def _tokenize_text(text: str) -> list[str]:
  """Normalizes text into alignment-friendly word tokens.

  Intentionally strips digits to match `normalize_text`, which also removes
  numbers before feeding text to the forced-alignment model. Keeping digits
  here would produce phantom tokens with no counterpart in `word_timestamps`.
  """
  normalized = (
    text.lower()
    .replace("â€™", "’")
    .replace("’", "’")
    .replace("&", " and ")
    .replace("/", " ")
  )
  return re.findall(r"[a-z]+(?:[‘-][a-z]+)*", normalized)


def _parse_ass_dialogue_chunks(
  ass_content: str,
  romanization: list[str] | None = None,
) -> list[SubtitleChunk]:
  """Parses ASS dialogue lines into timed subtitle chunks with word spans.

  When `romanization` is provided it must contain exactly one entry per
  Dialogue line, in file order; each chunk's `alignment_text` comes from it.
  When omitted, `alignment_text` falls back to the native dialogue text
  (English-only behavior, unchanged from before romanization existed).

  Known limitation: a Dialogue line whose `alignment_text` tokenizes to no
  words (e.g. a blank or punctuation-only romanization entry) is silently
  dropped from both the TTS narrative and the alignment transcript -- the
  burned-in subtitle for that line still renders (it comes from the raw
  `ass_content`, not from these chunks), but no voiceover audio is
  generated for it. A warning is logged when this happens.

  Raises:
    ValueError: If `romanization` is provided with the wrong entry count, or
      no usable dialogue chunks are found.
  """
  dialogue_lines = [
    line for line in ass_content.splitlines() if line.startswith("Dialogue:")
  ]
  if romanization is not None and len(romanization) != len(dialogue_lines):
    raise ValueError(
      f"romanization must have one entry per Dialogue line: got "
      f"{len(romanization)} entries for {len(dialogue_lines)} lines."
    )

  chunks: list[SubtitleChunk] = []
  word_index = 0
  for line_index, line in enumerate(dialogue_lines):
    parts = line.split(",", 9)
    if len(parts) <= 9:
      continue
    start_time = _parse_ass_timestamp(parts[1])
    end_time = _parse_ass_timestamp(parts[2])
    text = _clean_ass_dialogue_text(parts[9].strip())
    alignment_text = (
      romanization[line_index] if romanization is not None else text
    )
    tokens = _tokenize_text(alignment_text)
    if not text or not tokens:
      if text and not tokens:
        logger.warning(
          f"Dropping Dialogue line {line_index}: alignment_text "
          f"{alignment_text!r} has no tokenizable words. This line will "
          "have no voiceover audio."
        )
      continue
    start_word_index = word_index
    word_index += len(tokens)
    chunks.append(
      SubtitleChunk(
        text=text,
        alignment_text=alignment_text,
        start_time=start_time,
        end_time=end_time,
        start_word_index=start_word_index,
        end_word_index=word_index,
      )
    )

  if not chunks:
    raise ValueError("No dialogue chunks found in ASS content.")

  return chunks


def _subtitle_chunks_to_text(chunks: list[SubtitleChunk]) -> str:
  """Flattens subtitle chunks back into one narration script.

  Chunks are separated by a blank line so the TTS reads each as its own
  beat with a natural breath between them, and a trailing ellipsis follows
  the final chunk so the model has somewhere to trail off into instead of
  clipping the last word at the generation's stop condition. Both are pure
  punctuation/whitespace, not words -- unlike the "[pause]" marker
  previously used here, which is not a documented Gemini TTS audio tag
  (unlike genuine tags such as [whispers] or [sighs]) and could get
  literally vocalized as garbled text, especially in non-English narration.
  """
  return "\n\n".join(chunk.text for chunk in chunks) + "\n\n..."


def _align_subtitle_chunks_to_words(
  chunks: list[SubtitleChunk],
  word_timestamps: list[WordTimestamp],
) -> list[tuple[SubtitleChunk, float, float]]:
  """Matches subtitle chunks to recognized word timestamps sequentially.

  The matching is intentionally tolerant because STT may omit or slightly
  rewrite words from the generated narration. Starts use the matched word's
  actual start time. Ends use the matched end word plus a midpoint buffer
  toward the next recognized word when available.
  """
  aligned_segments: list[tuple[SubtitleChunk, float, float]] = []
  transcript_entries = [
    (token, word)
    for word in word_timestamps
    for token in _tokenize_text(word.word)
  ]
  transcript_tokens = [token for token, _ in transcript_entries]
  transcript_word_infos = [word for _, word in transcript_entries]
  total_script_words = chunks[-1].end_word_index if chunks else 0

  def _resolve_segment_start(start_index: int) -> float:
    return transcript_word_infos[start_index].start_time

  def _resolve_segment_end(end_index: int) -> float:
    end_time = transcript_word_infos[end_index].end_time
    next_index = end_index + 1
    if next_index < len(transcript_word_infos):
      next_start_time = transcript_word_infos[next_index].start_time
      if next_start_time > end_time:
        return (end_time + next_start_time) / 2
    return end_time

  cursor = 0
  for chunk in chunks:
    chunk_tokens = _tokenize_text(chunk.alignment_text)
    if not chunk_tokens:
      continue

    scan_cursor = cursor
    target_index = 0
    matched_indices: list[int] = []
    matched_token_count = 0

    search_limit = min(
      len(transcript_tokens),
      cursor
      + max(
        len(chunk_tokens) * _ALIGNMENT_SEARCH_WINDOW_MULTIPLE,
        _ALIGNMENT_SEARCH_MIN_WINDOW,
      ),
    )

    while scan_cursor < search_limit and target_index < len(chunk_tokens):
      if _tokens_match(
        chunk_tokens[target_index], transcript_tokens[scan_cursor]
      ):
        matched_indices.append(scan_cursor)
        matched_token_count += 1
        target_index += 1
        scan_cursor += 1
        continue

      if target_index + 1 < len(chunk_tokens) and _merged_tokens_match(
        chunk_tokens[target_index],
        chunk_tokens[target_index + 1],
        transcript_tokens[scan_cursor],
      ):
        matched_indices.extend([scan_cursor, scan_cursor])
        matched_token_count += 2
        target_index += 2
        scan_cursor += 1
        continue

      if scan_cursor + 1 < len(transcript_tokens) and _merged_tokens_match(
        transcript_tokens[scan_cursor],
        transcript_tokens[scan_cursor + 1],
        chunk_tokens[target_index],
      ):
        matched_indices.extend([scan_cursor, scan_cursor + 1])
        matched_token_count += 1
        target_index += 1
        scan_cursor += 2
        continue

      if target_index + 1 < len(chunk_tokens) and _tokens_match(
        chunk_tokens[target_index + 1],
        transcript_tokens[scan_cursor],
      ):
        logger.debug(
          "Skipping expected token during alignment: %r before %r in chunk %r.",
          chunk_tokens[target_index],
          chunk_tokens[target_index + 1],
          chunk.text,
        )
        target_index += 1
        continue

      if scan_cursor + 1 < len(transcript_tokens) and _tokens_match(
        chunk_tokens[target_index],
        transcript_tokens[scan_cursor + 1],
      ):
        logger.debug(
          "Skipping transcript token during alignment: %r before %r for chunk %r.",  # noqa: E501
          transcript_tokens[scan_cursor],
          transcript_tokens[scan_cursor + 1],
          chunk.text,
        )
        scan_cursor += 1
        continue

      scan_cursor += 1

    if not matched_indices:
      if not transcript_word_infos or total_script_words <= 0:
        raise ValueError(
          f"Unable to align subtitle chunk to transcribed audio: {chunk.text}"
        )

      estimated_start_index = min(
        len(transcript_word_infos) - 1,
        max(
          cursor,
          int(
            chunk.start_word_index
            / total_script_words
            * len(transcript_word_infos)
          ),
        ),
      )
      estimated_end_index = min(
        len(transcript_word_infos) - 1,
        max(
          estimated_start_index,
          int(
            max(chunk.end_word_index - 1, chunk.start_word_index)
            / total_script_words
            * len(transcript_word_infos)
          ),
        ),
      )

      logger.warning(
        "Falling back to estimated subtitle alignment for chunk %r.",
        chunk.text,
      )
      aligned_segments.append(
        (
          chunk,
          _resolve_segment_start(estimated_start_index),
          _resolve_segment_end(estimated_end_index),
        )
      )
      cursor = estimated_end_index + 1
      continue

    start_index = matched_indices[0]
    end_index = matched_indices[-1]

    if target_index != len(chunk_tokens):
      reverse_cursor = min(len(transcript_tokens) - 1, search_limit - 1)
      reverse_target_index = len(chunk_tokens) - 1
      reverse_matches: list[int] = []

      while reverse_cursor >= start_index and reverse_target_index >= 0:
        if _tokens_match(
          chunk_tokens[reverse_target_index], transcript_tokens[reverse_cursor]
        ):
          reverse_matches.append(reverse_cursor)
          reverse_target_index -= 1
        reverse_cursor -= 1

      if reverse_matches:
        end_index = max(reverse_matches)

      logger.warning(
        "Partial subtitle alignment accepted for chunk %r: matched %s/%s words.",  # noqa: E501
        chunk.text,
        matched_token_count,
        len(chunk_tokens),
      )

    aligned_segments.append(
      (
        chunk,
        _resolve_segment_start(start_index),
        _resolve_segment_end(end_index),
      )
    )
    cursor = end_index + 1

  return aligned_segments


def _detect_chunk_overruns(
  windows_and_audio: list[tuple[float, float]],
  *,
  min_relative: float = _OVERRUN_TOLERANCE_RELATIVE,
  min_absolute: float = _OVERRUN_TOLERANCE_ABSOLUTE,
) -> list[ChunkOverrun]:
  """Returns chunks whose audio overruns its ASS window past tolerance.

  A chunk is considered an overrun only when the audio runs past the window
  by more than `max(min_relative * window, min_absolute)` seconds, so tiny
  overruns the existing safety-net padding can absorb don't trigger an
  expensive refinement round-trip.
  """
  overruns: list[ChunkOverrun] = []
  for index, (window, audio) in enumerate(windows_and_audio):
    over_abs = audio - window
    if over_abs <= 0:
      continue
    tolerance = max(min_relative * window, min_absolute)
    if over_abs <= tolerance:
      continue
    over_pct = (over_abs / window) * 100.0 if window > 0 else float("inf")
    overruns.append(
      ChunkOverrun(
        index=index,
        window_seconds=window,
        audio_seconds=audio,
        over_percent=over_pct,
      )
    )
  return overruns


def _detect_dropped_phrases(
  word_timestamps: list[WordTimestamp],
  *,
  score_threshold: float = _DROP_SCORE_THRESHOLD,
  min_run: int = _MIN_DROPPED_RUN,
) -> list[DroppedPhrase]:
  """Returns runs of consecutive low-confidence words (likely dropped).

  A word counts as weak when its forced-alignment score is below
  `score_threshold`. Maximal runs of consecutive weak words whose length is at
  least `min_run` are reported. With the default `min_run = 2`, a single
  isolated weak word is tolerated (it may be a quiet function word or a benign
  one-phoneme miss); a run of two or more indicates a phrase the TTS skipped.

  Args:
    word_timestamps: Forced-alignment words for the full narration, in order.
    score_threshold: Exclusive upper bound below which a word is "weak".
    min_run: Minimum consecutive weak words to count as a dropped phrase.

  Returns:
    One `DroppedPhrase` per qualifying run, in order.
  """
  dropped: list[DroppedPhrase] = []
  run: list[int] = []

  def flush() -> None:
    if len(run) >= min_run:
      scores = [word_timestamps[i].score for i in run]
      dropped.append(
        DroppedPhrase(
          start_word_index=run[0],
          end_word_index=run[-1],
          words=tuple(word_timestamps[i].word for i in run),
          min_score=min(scores),
          mean_score=sum(scores) / len(scores),
        )
      )

  for index, word in enumerate(word_timestamps):
    if word.score < score_threshold:
      run.append(index)
    else:
      flush()
      run.clear()
  flush()
  return dropped


def _format_overrun_report(overruns: list[ChunkOverrun]) -> str:
  """Renders the compact overrun list the narrative_refiner agent consumes."""
  if not overruns:
    raise ValueError("Cannot format an empty overrun report.")
  return "\n".join(
    f"Line {o.index} (window {o.window_seconds:.2f}s, audio {o.audio_seconds:.2f}s, {round(o.over_percent)}% over) -- shorten."  # noqa: E501
    for o in overruns
  )


def _assemble_voice_instructions(pick: dict[str, str]) -> str:
  """Renders the voice_instructions string from a curated-list pick.

  Args:
    pick: Mapping with keys `audio_profile`, `voice_style`, `pace`, each
      pointing to a key in the corresponding curated dict.

  Raises:
    ValueError: If any pick value is missing or is not a key in the
      corresponding curated dict.
  """
  audio_profile_key = pick.get("audio_profile")
  voice_style_key = pick.get("voice_style")
  pace_key = pick.get("pace")

  if audio_profile_key not in AUDIO_PROFILES:
    raise ValueError(
      f"Unknown audio_profile pick: {audio_profile_key!r}. Expected one of {sorted(AUDIO_PROFILES)}."  # noqa: E501
    )
  if voice_style_key not in VOICE_STYLES:
    raise ValueError(
      f"Unknown voice_style pick: {voice_style_key!r}. Expected one of {sorted(VOICE_STYLES)}."  # noqa: E501
    )
  if pace_key not in PACE_OPTIONS:
    raise ValueError(
      f"Unknown pace pick: {pace_key!r}. Expected one of {sorted(PACE_OPTIONS)}."  # noqa: E501
    )

  return f"Read the following transcript based on the audio profile and director's note.\n\n# Audio Profile\n{AUDIO_PROFILES[audio_profile_key]}\n\n# Director's note\nStyle: {VOICE_STYLES[voice_style_key]}\nPace: {PACE_OPTIONS[pace_key]}\nAccent: a natural native accent for the narration language.\n\n## Context: Premium voice. High-impact delivery. Starts with a captivating, high-energy hook to immediately spark attention, maintaining a strong, consistent volume. Ends with a sharp, punchy finish that leaves the listener wanting more. Tone is polished, persuasive, and inviting.\n\n## Delivery rules: A blank line between lines marks a natural breath -- take it, don't rush into the next line. A trailing \"...\" is you trailing off into silence, not a word to pronounce. Fully articulate every word, including the very last word of the transcript: let its final consonant or vowel finish naturally before the recording ends, never clipped or cut short.\n\n## Transcript:"  # noqa: E501


def _resolve_voice_name(pick: dict[str, str]) -> str:
  """Resolves the picked prebuilt voice name, falling back to the default.

  The picker is asked to choose a `voice_name` from `VOICE_CONFIG`, but the
  field may be missing or name a voice outside the catalog. In either case we
  fall back to `DEFAULT_VOICE_NAME` ("Kore") so synthesis always has a voice.
  """
  voice_name = pick.get("voice_name")
  if voice_name in VOICE_CONFIG:
    return voice_name
  if voice_name:
    logger.warning(
      "Voice profile pick named unknown voice %r; falling back to %r.",
      voice_name,
      DEFAULT_VOICE_NAME,
    )
  return DEFAULT_VOICE_NAME


async def generate_voice_profile(
  ass_content: str,
  context: str | None = None,
) -> VoiceProfile:
  """Picks a voice persona for the script and returns the casting decision.

  Uses the `voice_profile_picker` text agent to choose one Audio Profile,
  one Voice Style, one Pace, and one prebuilt voice from the curated lists.
  The returned `VoiceProfile` carries those curated keys; the prebuilt
  `voice_name` is resolved against the catalog (defaulting to "Kore").

  Args:
    ass_content: Raw ASS narration the voice should suit.
    context: Optional extra context (e.g. storyboard mood/tone or the user
      prompt) so the casting reflects the broader video, not just the script.
  """
  agent = AgentFactory.create_text_agent(agent_name="voice_profile_picker")
  contents = [f"ASS content:\n{ass_content}"]
  if context:
    contents.append(f"Additional context:\n{context}")
  pick = await agent.generate_json_content_async(contents=contents)
  logger.info(f"Voice profile pick: {pick}")
  return VoiceProfile(
    audio_profile=pick.get("audio_profile", ""),
    voice_style=pick.get("voice_style", ""),
    pace=pick.get("pace", ""),
    voice_name=_resolve_voice_name(pick),
  )


async def _generate_and_align_voiceover(
  ass_content: str,
  voice_agent_builder,
  temp_dir: str,
  *,
  attempt_id: int,
  seed: int,
  romanization: list[str] | None = None,
) -> _VoiceoverAttempt:
  """Generate one full-pass voiceover and align it against the ASS chunks.

  Each attempt builds a fresh voice agent for `seed` (so regenerations vary
  while the voice persona stays constant), extracts per-chunk WAV segments, and
  records both the `(window_seconds, audio_seconds)` pair the overrun detector
  consumes and the per-word timestamps the drop detector consumes.

  `romanization`, when provided, supplies one ASCII entry per ASS Dialogue
  line; forced alignment matches against it while TTS synthesis still uses
  the native-script `ass_content` text.
  """
  voice_agent = voice_agent_builder(seed)

  subtitle_chunks = _parse_ass_dialogue_chunks(
    ass_content, romanization=romanization
  )
  narrative_text = _subtitle_chunks_to_text(subtitle_chunks)
  logger.info(
    f"[attempt {attempt_id}] Extracted narrative text for VO: {narrative_text}"
  )

  vo_file_paths = await voice_agent.generate_speech(
    text=narrative_text,
    output_dir=temp_dir,
  )
  local_vo_path = vo_file_paths[0]

  alignment_transcript = " ".join(
    chunk.alignment_text for chunk in subtitle_chunks
  )
  word_timestamps = align_audio_with_transcript(
    local_vo_path, alignment_transcript
  )
  aligned_segments = _align_subtitle_chunks_to_words(
    subtitle_chunks,
    word_timestamps,
  )

  timed_segment_paths: list[tuple[str, float, float]] = []
  windows_and_audio: list[tuple[float, float]] = []
  for index, (chunk, segment_start, segment_end) in enumerate(aligned_segments):
    local_segment_path = os.path.join(
      temp_dir, f"vo_attempt{attempt_id}_chunk{index}.wav"
    )
    segment_duration = ffmpeg.extract_audio_segment(
      input_path=local_vo_path,
      output_path=local_segment_path,
      start_time=segment_start,
      end_time=segment_end,
    )
    timed_segment_paths.append(
      (
        local_segment_path,
        chunk.start_time,
        max(chunk.end_time, chunk.start_time + segment_duration),
      )
    )
    windows_and_audio.append(
      (chunk.end_time - chunk.start_time, segment_duration)
    )

  return _VoiceoverAttempt(
    subtitle_chunks=subtitle_chunks,
    timed_segment_paths=timed_segment_paths,
    windows_and_audio=windows_and_audio,
    word_timestamps=word_timestamps,
  )


async def generate_voiceover_service(
  ass_content: str,
  bucket_name: str,
  voice_profile: VoiceProfile | None = None,
  romanization: list[str] | None = None,
) -> AudioMetadata:
  """Generate a subtitle-aligned voiceover track and upload it to GCS.

  Parses dialogue timings from the supplied ASS content, picks a voice
  persona that fits the script, generates one continuous voiceover with the
  native-audio agent, runs forced alignment against the script, then
  re-stitches the audio so every line sits at the timestamp the ASS file
  expects.

  When one or more chunks' audio overruns its ASS window past tolerance,
  a `narrative_refiner` agent is asked over a multi-turn chat to re-emit
  the ASS with the offending lines shortened. The voiceover is then
  regenerated end-to-end (preserving voice consistency) and re-checked.
  Up to `MAX_VOICEOVER_REFINEMENT_RETRIES` refinement turns are attempted;
  the existing `max(...)` end-time padding remains as the final safety net.
  When refinement happens, the refined ASS is returned in
  `AudioMetadata.refined_ass_content` so the caller can pass the matching
  subtitles to `render_final_video_service`.

  Args:
      ass_content: Raw ASS subtitle content with dialogue lines.
      bucket_name: GCS bucket to upload the stitched voiceover into.
      voice_profile: Optional pre-chosen casting selection (typically from
          `generate_narrative`, which has the video/storyboard context). When
          omitted, a profile is picked here from `ass_content` alone.
      romanization: Optional romanized transcript, one lowercase-ASCII entry
          per ASS Dialogue line (from generate_narrative). Required in
          practice for non-Latin-script narration -- without it, alignment
          falls back to the native dialogue text, which only works for
          English/Latin scripts.

  Returns:
      AudioMetadata for the uploaded WAV in gs://{bucket}/voiceovers/.
      `refined_ass_content` is set when one or more refinement turns ran.
  """
  logger.info("Generating voiceover from ASS content.")

  with tempfile.TemporaryDirectory() as temp_dir:
    if voice_profile is None:
      voice_profile = await generate_voice_profile(ass_content)
    pick = asdict(voice_profile)

    def make_voice_agent(seed: int):
      return AgentFactory.create_native_audio_agent(
        custom_config={
          "agent_name": "voiceover_agent",
          "model_config": {
            "speech_config": {
              "voice_config": {
                "prebuilt_voice_config": {
                  "voice_name": _resolve_voice_name(pick),
                }
              },
            },
            "temperature": 1.0,
            "response_modalities": ["audio"],
            "seed": seed,
          },
          "voice_instructions": _assemble_voice_instructions(pick),
        },
      )

    current_ass = ass_content
    refined_ass: str | None = None
    current_romanization = romanization
    refiner_agent = None
    base_seed = 42
    file_attempt = 0
    regen_retries = 0
    refine_retries = 0

    attempt = await _generate_and_align_voiceover(
      current_ass,
      make_voice_agent,
      temp_dir,
      attempt_id=file_attempt,
      seed=base_seed,
      romanization=current_romanization,
    )

    while True:
      dropped = _detect_dropped_phrases(attempt.word_timestamps)
      if dropped and regen_retries < MAX_VOICEOVER_REGENERATION_RETRIES:
        regen_retries += 1
        file_attempt += 1
        logger.warning(
          f"[drop regen {regen_retries}/{MAX_VOICEOVER_REGENERATION_RETRIES}] {len(dropped)} dropped phrase(s); regenerating with seed {base_seed + file_attempt}: {[d.words for d in dropped]}"  # noqa: E501
        )
        attempt = await _generate_and_align_voiceover(
          current_ass,
          make_voice_agent,
          temp_dir,
          attempt_id=file_attempt,
          seed=base_seed + file_attempt,
          romanization=current_romanization,
        )
        continue

      overruns = _detect_chunk_overruns(attempt.windows_and_audio)
      if overruns and refine_retries < MAX_VOICEOVER_REFINEMENT_RETRIES:
        refine_retries += 1
        file_attempt += 1
        logger.warning(
          f"[refinement retry {refine_retries}/{MAX_VOICEOVER_REFINEMENT_RETRIES}] {len(overruns)} chunks overrun: indices={[o.index for o in overruns]}"  # noqa: E501
        )
        overrun_report = _format_overrun_report(overruns)
        if refiner_agent is None:
          refiner_agent = AgentFactory.create_text_agent(
            agent_name="narrative_refiner"
          )
          narrative_json = json.dumps(
            {
              "ass_content": current_ass,
              "romanization": current_romanization or [],
            },
            ensure_ascii=False,
          )
          refiner_message = (
            f"Original narrative JSON:\n{narrative_json}\n\n"
            f"Overrun report:\n{overrun_report}"
          )
        else:
          refiner_message = f"Overrun report:\n{overrun_report}"

        refined = await refiner_agent.generate_json_content_async(
          contents=refiner_message
        )
        current_ass = str(refined.get("ass_content", "")).strip()
        if not current_ass:
          raise ValueError("narrative_refiner returned empty ass_content.")
        if current_romanization is not None:
          current_romanization = [
            str(entry) for entry in refined.get("romanization", [])
          ]
        refined_ass = current_ass

        attempt = await _generate_and_align_voiceover(
          current_ass,
          make_voice_agent,
          temp_dir,
          attempt_id=file_attempt,
          seed=base_seed + file_attempt,
          romanization=current_romanization,
        )
        continue

      break

    remaining_dropped = _detect_dropped_phrases(attempt.word_timestamps)
    if remaining_dropped:
      logger.warning(
        f"Voiceover still missing {len(remaining_dropped)} phrase(s) after {MAX_VOICEOVER_REGENERATION_RETRIES} regeneration retries; accepting last result: {[d.words for d in remaining_dropped]}"  # noqa: E501
      )

    remaining_overruns = _detect_chunk_overruns(attempt.windows_and_audio)
    if remaining_overruns:
      logger.warning(
        f"Voiceover still has {len(remaining_overruns)} overrun chunks after {MAX_VOICEOVER_REFINEMENT_RETRIES} refinement retries; accepting last result with end-time padding safety net."  # noqa: E501
      )

    stitched_vo_path = os.path.join(temp_dir, "voiceover_timed.wav")
    ffmpeg.concat_audio_segments(attempt.timed_segment_paths, stitched_vo_path)
    normalized_vo_path = ffmpeg.normalize_loudness(
      stitched_vo_path,
      target_i=-16.0,
      target_lra=7.0,
      target_tp=-2.0,
      sample_rate=24000,
      audio_channels=1,
    )
    duration_seconds = ffmpeg.get_video_duration(normalized_vo_path)

    uploaded_uri = upload_file_to_gcs(
      file_path=normalized_vo_path,
      gcs_uri=(
        f"gs://{bucket_name}/voiceovers/voiceover_{uuid.uuid4().hex}.wav"
      ),
      content_type="audio/wav",
    )

  logger.info(f"Voiceover uploaded: {uploaded_uri}")
  return AudioMetadata(
    gcs_uri=uploaded_uri,
    duration_seconds=duration_seconds,
    refined_ass_content=refined_ass,
  )
