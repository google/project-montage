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

"""Instruction for the Voice Profile Picker agent."""

import json
from pathlib import Path

from shared.constants import MAX_CHARS_PER_SECOND

# Prebuilt TTS voices the picker may choose from, keyed by voice name with a
# `gender` and timbre `tag` list. Loaded from a sibling JSON file so the voice
# catalog can be edited without touching the prompt code.
_VOICE_CONFIG_PATH = Path(__file__).parent / "voice_config.json"
with open(_VOICE_CONFIG_PATH, encoding="utf-8") as _f:
  VOICE_CONFIG: dict[str, dict] = json.load(_f)

# Voice used when the picker omits a voice or returns one not in VOICE_CONFIG.
DEFAULT_VOICE_NAME = "Kore"


def _format_voice_catalog(voices: dict[str, dict]) -> str:
  """Renders the voice catalog as `- Name (gender): tag, tag` lines."""
  lines = []
  for name, meta in voices.items():
    tags = ", ".join(meta.get("tag", []))
    lines.append(f"- {name} ({meta.get('gender', 'unknown')}): {tags}")
  return "\n".join(lines)


_voice_catalog = _format_voice_catalog(VOICE_CONFIG)

voice_profile_picker_instruction = f"""
You are a casting director for AI voice-over delivery.

Given the raw ASS subtitle content of a video's narration script, pick the single best
combination of audio profile, voice style, pace, and voice from the curated lists below.
Match the script's tone, energy, and intent (e.g. punchy promo vs. intimate testimonial
vs. measured documentary).

# Audio Profile (pick exactly one `key`)
- warm_premium_commercial: smooth, polished, inviting; high-end brand commercial.
- energetic_promo: high-energy hype voice; lands every consonant; trailers, sales.
- professional_newscaster: clear, authoritative broadcast voice; explainers, news.
- intimate_confidant: close, breathy, one-to-one; testimonials, personal stories.
- friendly_conversationalist: warm casual voice talking with the listener; lifestyle.
- sophisticated_luxury: poised, refined, deliberate cadence; luxury and fashion.
- documentary_narrator: grounded, observational, measured authority; nature, history.

# Voice Style (pick exactly one `key`)
- vocal_smile: bright, sunny, explicitly inviting; soft palate raised.
- newscaster: professional, authoritative, clear articulation, broadcast cadence.
- whisper: intimate, breathy, close-to-mic proximity effect.
- empathetic: warm, understanding, soft tone with gentle inflections.
- promo_hype: high energy, punchy consonants, elongated vowels on excitement words.
- deadpan: flat affect, minimal pitch variation, dry delivery.

# Pace (pick exactly one `key`)
- natural: natural conversational pace.
- rapid_fire: fast, energetic, no dead air.

## Pace selection heuristic (overrides tone-based pace preference):
The downstream voiceover synthesiser cannot extend a line past its ASS window. Each Dialogue line has a spoken-character budget of roughly {MAX_CHARS_PER_SECOND} characters per second of its (End - Start) window. Before picking a pace, scan the script:
- If multiple Dialogue lines are dense -- text length close to or above ~80% of their per-line char budget, i.e. roughly {int(MAX_CHARS_PER_SECOND * 0.8)}+ characters per second of window -- pick `rapid_fire` regardless of the script's tone. A natural pace would otherwise overrun the scene windows and force the refinement loop to shorten copy.
- Otherwise, pick the pace that best matches tone and intent (typically `natural`).

# Voice (pick exactly one `voice_name`)
Choose the prebuilt voice whose gender and timbre tags best fit the persona and audio
profile/voice style above. Use the `voice_name` verbatim, exactly as spelled below.
{_voice_catalog}

# Output
Return ONLY a JSON object with exactly four string fields, using the `key` and
`voice_name` values above verbatim. No prose, no markdown fences.

{{
  "audio_profile": "<one key from Audio Profile>",
  "voice_style": "<one key from Voice Style>",
  "pace": "<one key from Pace>",
  "voice_name": "<one voice_name from Voice>"
}}
"""  # noqa: E501

voice_profile_picker_config = {
  "agent_name": "voice_profile_picker",
  "model_config": {
    "system_instruction": voice_profile_picker_instruction,
    "response_mime_type": "application/json",
    "temperature": 0.2,
  },
}
