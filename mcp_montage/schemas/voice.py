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

"""Voice-casting schema shared between narrative and voiceover tools."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field


@dataclass
class VoiceProfile:
  """Casting selection for a voiceover track.

  Produced by the `voice_profile_picker` -- ideally at narrative time, where
  the video and storyboard context is available -- and consumed by
  `generate_voiceover`. The three curated keys map into speech_service's
  `AUDIO_PROFILES`, `VOICE_STYLES`, and `PACE_OPTIONS`; `voice_name` is a
  prebuilt Gemini TTS voice from `voice_config.json`.
  """

  audio_profile: Annotated[
    str,
    Field(
      description="Audio profile key (e.g. warm_premium_commercial, energetic_promo)."  # noqa: E501
    ),
  ]
  voice_style: Annotated[
    str,
    Field(
      description="Voice style key (e.g. vocal_smile, newscaster, empathetic)."  # noqa: E501
    ),
  ]
  pace: Annotated[
    str,
    Field(description="Pace key (e.g. natural, rapid_fire)."),
  ]
  voice_name: Annotated[
    str,
    Field(
      description="Prebuilt Gemini TTS voice name (e.g. Kore, Sulafat, Charon)."  # noqa: E501
    ),
  ]
