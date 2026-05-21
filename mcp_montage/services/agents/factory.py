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

"""Factory class to create different types of agents."""

from pathlib import Path
from typing import Any

from services.agents import image_agent, text_agent, video_agent
from services.agents.config import (
  asset_selector_config,
  describing_image_config,
  generative_cropping_config,
  image_prompt_builder_config,
  image_to_storyboard_writer_config,
  music_prompt_builder_config,
  narrative_writer_config,
  storyboard_writer_config,
  video_prompt_builder_config,
)


class AgentFactory:
  PROMPT_DIR = Path(__file__).parent / "config"

  @classmethod
  def create_text_agent(
    cls,
    agent_name: str,
    custom_config: dict[str, Any] | None = None,
  ) -> text_agent.GeminiAgent:
    if custom_config is not None:
      return text_agent.GeminiAgent(**custom_config)
    elif agent_name == "image_prompt_builder":
      return text_agent.GeminiAgent(**image_prompt_builder_config)
    elif agent_name == "image_to_storyboard_writer":
      return text_agent.GeminiAgent(**image_to_storyboard_writer_config)
    elif agent_name == "storyboard_writer":
      return text_agent.GeminiAgent(**storyboard_writer_config)
    elif agent_name == "asset_selector":
      return text_agent.GeminiAgent(**asset_selector_config)
    elif agent_name == "video_prompt_builder":
      return text_agent.GeminiAgent(**video_prompt_builder_config)
    elif agent_name == "describing_image":
      return text_agent.GeminiAgent(**describing_image_config)
    elif agent_name == "music_prompt_builder":
      return text_agent.GeminiAgent(**music_prompt_builder_config)
    elif agent_name == "narrative_writer":
      return text_agent.GeminiAgent(**narrative_writer_config)
    else:
      raise ValueError(f"Unknown agent name: {agent_name}")

  @classmethod
  def create_video_agent(
    cls,
    agent_name: str = "video_generation",
    custom_config: dict[str, Any] | None = None,
  ) -> video_agent.VeoAgent:
    if custom_config is not None:
      return video_agent.VeoAgent(**custom_config)
    elif agent_name == "video_generation":
      return video_agent.VeoAgent()
    else:
      raise ValueError(f"Unknown agent name: {agent_name}")

  @classmethod
  def create_image_agent(
    cls,
    agent_name: str = "image_generation",
    custom_config: dict[str, Any] | None = None,
  ) -> image_agent.GeminiImageAgent:
    if custom_config is not None:
      return image_agent.GeminiImageAgent(**custom_config)
    elif agent_name == "image_generation":
      return image_agent.GeminiImageAgent()
    elif agent_name == "generative_cropping":
      return image_agent.GeminiImageAgent(**generative_cropping_config)
    else:
      raise ValueError(f"Unknown agent name: {agent_name}")
