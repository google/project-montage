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

"""Native audio generation agent using Gemini TTS."""

import io
import wave
from typing import Any

from google.genai import types
from schemas.media import RawMediaItem
from shared.config import config
from tenacity import retry, stop_after_attempt, wait_exponential
from utils import log
from utils import storage as storage_utils

from services.agents import base_agent

logger = log.get_logger()


class NativeAudioAgent(base_agent.BaseAgent):
  """Native audio generation agent using Gemini TTS.

  Attributes:
  agent_name (str): The name of the agent.
  model_name (str): The name of the model.
  model_config (types.GenerateContentConfig): The configuration for the model.
  """

  voice_instructions: str = ""

  def __init__(
    self,
    agent_name: str = "Native audio generation model",
    model_name: str = config.get("tts_model", "gemini-3.1-flash-tts-preview"),
    model_config: dict[str, Any] | None = None,
    automatic_function_calling: bool = False,
    voice_instructions: str | None = None,
  ):
    if model_config is None:
      model_config = {"response_modalities": ["AUDIO"]}
    super().__init__(
      agent_name=agent_name,
      model_name=model_name,
      model_config=model_config,
      automatic_function_calling=automatic_function_calling,
    )
    self.voice_instructions = voice_instructions or ""

  def _pcm_to_wav(
    self,
    pcm_data: bytes,
    channels: int = 1,
    rate: int = 24000,
    sample_width: int = 2,
  ) -> bytes:
    """Converts raw PCM data to WAV format bytes.

    Args:
        pcm_data: The raw PCM data.
        channels: Number of audio channels.
        rate: Sample rate in Hz.
        sample_width: Sample width in bytes.

    Returns:
        The WAV file as bytes.
    """
    with io.BytesIO() as wav_io:
      with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)
      return wav_io.getvalue()

  @retry(
    wait=wait_exponential(min=5, max=60, multiplier=2),
    stop=stop_after_attempt(5),
    reraise=True,
  )
  async def generate_speech(
    self,
    text: str,
    output_dir: str,
    voice_name: str | None = None,
    language_code: str | None = None,
    output_gcs_uri: str | None = None,
    speech_config: types.SpeechConfig | None = None,
    generate_content_config: types.GenerateContentConfig | None = None,
  ) -> list[str]:
    """Generates speech from text and saves it as a WAV file.

    Args:
        text: The text to convert to speech.
        output_dir: Local directory to save the audio file.
        voice_name: The name of the prebuilt voice to use.
        language_code: The language code for the speech.
        output_gcs_uri: Optional GCS URI to upload the audio file.
        speech_config: Optional custom speech configuration.
        generate_content_config: Optional custom generate content configuration.

    Returns:
        List of saved file paths or GCS URIs.
    """
    logger.info(f"Generating speech using {self.model_name}")
    logger.debug(self._build_request_log(text))

    # Build custom config if provided, otherwise use defaults
    config_to_use = generate_content_config or types.GenerateContentConfig(
      **{
        k: v
        for k, v in self.model_config.__dict__.items()
        if not k.startswith("_")
      },
    )

    # Override speech config if provided, else use voice_name if available
    if speech_config:
      config_to_use.speech_config = speech_config
    elif voice_name:
      config_to_use.speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
          prebuilt_voice_config=types.PrebuiltVoiceConfig(
            voice_name=voice_name,
          )
        ),
      )

    if language_code and config_to_use.speech_config:
      # Set language code on speech config
      config_to_use.speech_config.language_code = language_code  # type: ignore[attr-defined]

    try:
      response = await self.genai_client.aio.models.generate_content(
        model=self.model_name,
        contents=self.voice_instructions + text,
        config=config_to_use,
      )

      # Extract PCM data
      if (
        not response.candidates
        or not response.candidates[0].content
        or not response.candidates[0].content.parts
      ):
        raise ValueError("No content generated in the response.")

      part = response.candidates[0].content.parts[0]
      if not part.inline_data or not part.inline_data.data:
        raise ValueError("No audio data found in the response.")

      pcm_data = part.inline_data.data
      wav_data = self._pcm_to_wav(pcm_data)

      media_item = RawMediaItem(data=wav_data, mime_type="audio/wav")

      return storage_utils.save_media_batch(
        [media_item],
        output_dir,
        output_gcs_uri,
        file_prefix="audio",
      )

    except Exception as err:
      logger.error(f"Error generating speech: {err}")
      raise err
