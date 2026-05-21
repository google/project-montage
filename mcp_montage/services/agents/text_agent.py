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

"""Base class for Text generation model."""

import json
from typing import Any

from google.genai import types
from shared.config import config
from tenacity import retry, stop_after_attempt, wait_exponential
from utils import log

from services.agents import base_agent

logger = log.get_logger()


class GeminiAgent(base_agent.BaseAgent):
  """Base class for gemini agentic models.

  Attributes:
  agent_name (str): The name of the agent.
  model_name (str): The name of the model.
  model_config (types.GenerateContentConfig): The configuration for the model.
  """

  agent_name: str
  model_name: str
  model_config: types.GenerateContentConfig

  def __init__(
    self,
    agent_name: str,
    model_name: str = config.get("gemini_model", "gemini-3.1-flash-lite"),
    model_config: dict[str, Any] | None = None,
    automatic_function_calling: bool = False,
  ):
    if model_config is None:
      model_config = {}
    super().__init__(
      agent_name=agent_name,
      model_name=model_name,
      model_config=model_config,
      automatic_function_calling=automatic_function_calling,
    )

  @retry(
    wait=wait_exponential(min=5, max=60, multiplier=2),
    stop=stop_after_attempt(5),
  )
  async def generate_content_async(
    self,
    contents: types.ContentUnionDict,
  ):
    """Generates content asynchronously.

    Args:
      contents: The contents to generate.

    Returns:
      The generated content.
    """
    logger.info(f"Invoking {self.agent_name}")
    logger.debug(self._build_request_log(contents))
    try:
      resp: types.GenerateContentResponse = (
        await self.async_chat_session.send_message(message=contents)
      )
      assert resp.text is not None
    except Exception as err:
      logger.error(err)
      raise err
    logger.debug(self._build_response_log(resp))
    return resp.text

  @retry(
    wait=wait_exponential(min=5, max=60, multiplier=2),
    stop=stop_after_attempt(5),
  )
  async def generate_json_content_async(
    self,
    contents: types.ContentUnionDict,
  ) -> dict[str, Any]:
    """Generates content asynchronously and returns it as a JSON object.
    Args:
      contents: The contents to generate.

    Returns:
      The generated content as a JSON object.
    """
    logger.info(f"Invoking {self.agent_name}")
    logger.debug(self._build_request_log(contents))
    try:
      resp: types.GenerateContentResponse = (
        await self.async_chat_session.send_message(message=contents)
      )
      assert resp.text is not None

      logger.debug(self._build_response_log(resp))

      resp_json = json.loads(resp.text)

      # Case when the response is a list of dicts, convert it to a single dict
      if isinstance(resp_json, list):
        resp_json_fixed = {}
        for item in resp_json:
          for k, v in item.items():
            resp_json_fixed[k] = v
        resp_json = resp_json_fixed

    except Exception as err:
      logger.error(err)
      raise err

    return resp_json

  @retry(
    wait=wait_exponential(min=5, max=60, multiplier=2),
    stop=stop_after_attempt(5),
  )
  async def generate_json_array_content_async(
    self,
    contents: types.ContentUnionDict,
  ) -> list[dict[str, Any]]:
    """Generates content asynchronously and returns it as a JSON object.
    Args:
      contents: The contents to generate.

    Returns:
      The generated content as a JSON object.
    """
    logger.info(f"Invoking {self.agent_name}")
    logger.debug(self._build_request_log(contents))
    try:
      resp: types.GenerateContentResponse = (
        await self.async_chat_session.send_message(message=contents)
      )
      assert resp.text is not None
      logger.debug(self._build_response_log(resp))

      resp_json = json.loads(resp.text)

    except Exception as err:
      logger.error(err)
      raise err

    return resp_json
