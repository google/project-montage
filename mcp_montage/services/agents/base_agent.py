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

"""Base class for agentic model."""

from functools import cached_property
from typing import Any

from google import genai
from google.genai import chats, types
from shared.constants import (
  GOOGLE_API_KEY,
  GOOGLE_CLOUD_LOCATION,
  GOOGLE_CLOUD_PROJECT,
  GOOGLE_GENAI_USE_VERTEXAI,
)
from utils import log

logger = log.get_logger()


class BaseAgent:
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
    model_name: str,
    model_config: dict[str, Any] | None = None,
    automatic_function_calling: bool = False,
  ):
    self.agent_name = agent_name
    self.model_name = model_name
    if isinstance(model_config, types.GenerateContentConfig):
      self.model_config = model_config
    else:
      config = model_config or {}
      self.model_config = types.GenerateContentConfig(**config)
    if not automatic_function_calling:
      self.model_config.automatic_function_calling = (
        types.AutomaticFunctionCallingConfig(disable=True)
      )  # noqa: E501

  @cached_property
  def genai_client(self) -> genai.Client:
    """Provides the api client.

    Returns:
    Client for making Gemini requests.
    """
    if GOOGLE_GENAI_USE_VERTEXAI:
      logger.info(f"Using Vertex AI for {self.model_name} requests. ")
      return genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location=GOOGLE_CLOUD_LOCATION
        if "preview" not in self.model_name
        else "global",
      )
    logger.info(f"Using Gemini API for {self.model_name} requests. ")
    return genai.Client(
      api_key=GOOGLE_API_KEY,
    )

  @cached_property
  def async_chat_session(self) -> chats.AsyncChat:
    """Provides the chat session.

    Returns:
    The chat session.
    """

    return self.genai_client.aio.chats.create(
      model=self.model_name,
      config=self.model_config,
      history=None,
    )

  def _build_request_log(
    self,
    contents: types.ContentUnionDict,
  ) -> str:
    if isinstance(contents, list):
      contents_logs: list[Any] = []
      for content in contents:
        if isinstance(content, str):
          contents_logs.append(content)
        else:
          contents_logs.append(type(content))
    else:
      contents_logs = [contents]
    return f"""
    LLM Request:
    -----------------------------------------------------------
    Agent name:
    {self.agent_name}
    -----------------------------------------------------------
    Contents:
    {contents_logs}
    -----------------------------------------------------------
    """

  def _build_response_log(self, resp: types.GenerateContentResponse) -> str:
    if not resp.text:
      return "LLM Response: No text response received."

    return f"""
    LLM Response:
    -----------------------------------------------------------
    Agent name:
    {self.agent_name}
    -----------------------------------------------------------
    Text:
    {resp.text}
    -----------------------------------------------------------
    """
