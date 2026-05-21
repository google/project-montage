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

"""State utilities for managing agent state and tool callbacks."""

import io
import logging
import uuid
from typing import Any

import json_repair
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from PIL import Image
from shared.constants import GCS_INGREDIENT_IMAGES_FOLDER

from utils.storage import upload_image_to_gcs


def save_asset_selector_response_to_state(
  tool_context: ToolContext, tool_response: dict[str, Any]
) -> None:
  """Saves the selected assets to the agent's state."""
  logging.info("Callback: Saving selected assets to state.")
  state = tool_context.state
  if not tool_response["content"]:
    return
  contents = tool_response["content"]
  asset_images_uri: list[str] = []
  for content in contents:
    if content["text"]:
      content_object = json_repair.loads(content["text"])
      if isinstance(content_object, dict):
        asset_images_uri.append(content_object.get("gcs_uri", ""))
      else:
        asset_images_uri.append(content["text"])
  state["selected_assets_metadata"] = content["text"]
  state["asset_images_uri"] = asset_images_uri


def save_storyboard_to_state(
  tool_context: ToolContext, tool_response: dict[str, Any]
) -> None:
  """Saves the storyboard to the agent's state."""
  logging.info("Callback: Saving storyboard to state.")
  state = tool_context.state
  storyboard = ""
  if not tool_response["content"]:
    return
  contents = tool_response["content"]
  for content in contents:
    if content["text"]:
      storyboard += content["text"]

  if storyboard:
    repaired_storyboard = json_repair.loads(storyboard)
    if isinstance(repaired_storyboard, dict):
      state["storyboard"] = repaired_storyboard
      visual_description_list: list[str] = []
      duration_list: list[bool] = []
      image_generation_request_list: list[Any] = []
      for shot in repaired_storyboard.get("storyboard", []):
        visual_description = shot.get("visual_description", "")
        visual_description_list.append(visual_description)
        base_images = shot.get("base_images", [])
        image_generation_request_list.append(
          {
            "visual_description": visual_description,
            "reference_images": base_images,
          }
        )
        duration = shot.get("scene_duration", 0)
        duration_list.append(duration)
      state["visual_description_list"] = visual_description_list
      state["duration"] = duration_list
      state["image_generation_request"] = image_generation_request_list
    else:
      # If not a dict, store the pure text and continue
      state["storyboard"] = storyboard
      state["visual_description_list"] = []
      state["duration"] = []
      state["image_generation_request"] = []


def save_storyboard_images_uri_to_state(
  tool_context: ToolContext,
  tool_response: dict[str, Any],
  tool_name: str = "generate_images",
) -> None:
  """Saves the storyboard image uri to the agent's state."""
  logging.info("Callback: Saving storyboard image uri to state.")
  state = tool_context.state
  if not tool_response["content"]:
    return
  contents = tool_response["content"]
  video_generation_request_list: list[dict[str, str | None]] = []
  visual_description_list = state.get("visual_description_list", [])
  duration_list = state.get("duration", [])
  for i, content in enumerate(contents):
    if content["text"]:
      content_object = json_repair.loads(content["text"])
      if isinstance(content_object, dict):
        gcs_uri = content_object.get("gcs_uri", [])
      else:
        gcs_uri = content["text"]
      try:
        video_generation_request_list.append(
          {
            "gcs_uri": gcs_uri,
            "prompt": visual_description_list[i],
            "duration": duration_list[i],
          }
        )
      except Exception as e:
        logging.error(f"Error in video_generation_request_list: {e}")
        continue
  if tool_name == "generate_images":
    state["video_generation_request_list"] = video_generation_request_list
  elif tool_name == "resize_image":
    state["video_generation_request_list_resize"] = (
      video_generation_request_list
    )


def save_storyboard_videos_uri_to_state(
  tool_context: ToolContext, tool_response: dict[str, Any]
) -> None:
  """Saves the storyboard video uri to the agent's state."""
  logging.info("Callback: Saving storyboard video uri to state.")
  state = tool_context.state
  if not tool_response["content"]:
    return
  contents = tool_response["content"]
  storyboard_videos_uri_list: list[str] = []
  for content in contents:
    if content["text"]:
      content_object = json_repair.loads(content["text"])
      if isinstance(content_object, dict):
        storyboard_videos_uri_list = content_object.get("gcs_uri", [])
      else:
        storyboard_videos_uri_list = content["text"]
  state["storyboard_videos_uri"] = storyboard_videos_uri_list


def save_concatenated_video_uri_to_state(
  tool_context: ToolContext, tool_response: dict[str, Any]
) -> None:
  """Saves the concatenated video uri to the agent's state."""
  logging.info("Callback: Saving concatenated video uri to state.")
  state = tool_context.state
  if not tool_response["content"]:
    return
  contents = tool_response["content"]
  concatenated_video_uri: str = ""
  for content in contents:
    if content["text"]:
      content_object = json_repair.loads(content["text"])
      if isinstance(content_object, dict):
        concatenated_video_uri = content_object.get("gcs_uri", [])
      else:
        concatenated_video_uri = content["text"]
  state["concatenated_video_uri"] = concatenated_video_uri


def save_video_with_bgm_url_to_state(
  tool_context: ToolContext, tool_response: dict[str, Any]
) -> None:
  """Saves the video with bgm url to the agent's state."""
  logging.info("Callback: Saving video with bgm url to state.")
  state = tool_context.state
  if not tool_response["content"]:
    return
  contents = tool_response["content"]
  video_bgm_url: str = ""
  for content in contents:
    if content["text"]:
      content_object = json_repair.loads(content["text"])
      if isinstance(content_object, dict):
        video_bgm_url = content_object.get("gcs_uri", [])
      else:
        video_bgm_url = content["text"]
  state["video_bgm_url"] = video_bgm_url


def after_tool_callback(
  tool: BaseTool,
  args: dict[str, Any],
  tool_context: ToolContext,
  tool_response: dict[str, Any],
) -> None:
  logging.info("Callback: after_tool_callback invoked.")
  tool_name = tool.name
  match tool_name:
    case "select_asset":
      save_asset_selector_response_to_state(tool_context, tool_response)
    case "generate_storyboard_by_text":
      save_storyboard_to_state(tool_context, tool_response)
    case "generate_storyboard_by_image":
      save_storyboard_to_state(tool_context, tool_response)
    case "generate_images":
      save_storyboard_images_uri_to_state(
        tool_context, tool_response, tool_name
      )
    case "resize_image":
      save_storyboard_images_uri_to_state(
        tool_context, tool_response, tool_name
      )
    case "generate_videos":
      save_storyboard_videos_uri_to_state(tool_context, tool_response)
    case "concatenate_videos":
      save_concatenated_video_uri_to_state(tool_context, tool_response)
    case "generate_bgm_and_merge":
      save_video_with_bgm_url_to_state(tool_context, tool_response)
    case _:
      logging.warning(
        f"Callback: No matching tool for after_tool_callback: {tool_name}"
      )


def before_agent_callback(callback_context: CallbackContext):
  logging.info("before_agent_callback")
  user_content = callback_context.user_content
  state = callback_context.state

  # initialize state
  state_defaults = {
    "visual_description_list": [],
    "uploaded_images_gcs_uri": [],
    "selected_assets_metadata": [],
    "asset_images_uri": [],
    "image_generation_request": [],
    "video_generation_request_list": [],
    "video_generation_request_list_resize": [],
    "storyboard_videos_uri": [],
    "concatenated_video_uri": "",
  }
  for key, default in state_defaults.items():
    if state.get(key, default) == default:
      state[key] = default
  state["ingredient_images_folder"] = GCS_INGREDIENT_IMAGES_FOLDER

  # upload user content images to gcs
  if not user_content or not user_content.parts:
    logging.info("Callback: No content or parts found in user_content.")
    return

  uploaded_images_folder_id = str(uuid.uuid4().hex[:10])
  state["uploaded_images_folder_id"] = uploaded_images_folder_id

  for part in user_content.parts:
    if (
      hasattr(part, "inline_data")
      and part.inline_data is not None
      and getattr(part.inline_data, "mime_type", "").startswith("image/")
    ):
      image_data = part.inline_data.data
      if image_data is None:
        logging.warning("Callback: Image data is None, skipping image upload.")
        continue
      image = Image.open(io.BytesIO(image_data))
      output_file_name = f"{str(uuid.uuid4().hex[:10])}.png"
      output_folder = "user_uploads/" + uploaded_images_folder_id
      gcs_uri = upload_image_to_gcs(image, output_file_name, output_folder)
      state["uploaded_images_gcs_uri"].append(gcs_uri)
      logging.info(
        f"Callback: Uploaded image saved to GCS at {gcs_uri} and state updated."
      )
