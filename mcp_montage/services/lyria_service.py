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

"""Service for generating music using the Lyria API."""

import base64
import io
import json
import random
import tempfile

from pydub import AudioSegment, effects
from shared.constants import (
  GOOGLE_CLOUD_LOCATION,
  GOOGLE_CLOUD_PROJECT,
)
from utils import log
from utils.google_api import send_request_to_google_api

_LYRIA_ENDPOINT = f"https://aiplatform.googleapis.com/v1/projects/{GOOGLE_CLOUD_PROJECT}/locations/{GOOGLE_CLOUD_LOCATION}/publishers/google/models/lyria-002:predict"

logger = log.get_logger()


async def generate_music(
  prompt: str,
  local_dir: str | None = None,
) -> str:
  """Generates music using the Lyria API.

  Args:
      prompt: The prompt describing the music to generate.
      local_dir: (Optional) Local directory to save the generated music.

  Returns:
      Path to the generated music file.
  """
  seed = random.randint(0, 1000000)

  with tempfile.NamedTemporaryFile(
    suffix=".wav", dir=local_dir, delete=False
  ) as tmp_file:
    output_bgm_path = tmp_file.name

  req = {
    "instances": [
      {
        "prompt": prompt,
        "negative_prompt": "",
        "seed": seed,
      }
    ],
    "parameters": {},
  }

  logger.info(f"Input request to lyria: {req}")

  try:
    lyria_response = await send_request_to_google_api(_LYRIA_ENDPOINT, req)
    lyria_response_json = json.loads(lyria_response)
    logger.info("Lyria get Response")

    bytes_b64 = lyria_response_json["predictions"][0]["bytesBase64Encoded"]
    decoded_audio_data = base64.b64decode(bytes_b64)

    audio_segment = AudioSegment.from_file(
      file=io.BytesIO(decoded_audio_data),
      format="raw",
      frame_rate=48000,
      sample_width=2,
      channels=2,
    )
    audio_segment_norm = effects.normalize(audio_segment)
    audio_segment_norm.export(output_bgm_path, format="wav")
    logger.info(f"Save BGM Audio Successful: {output_bgm_path}")

    return output_bgm_path

  except Exception as e:
    raise ValueError(f"Generate Music Error: {e}") from e
