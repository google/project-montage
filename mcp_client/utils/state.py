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

from google.adk.agents.callback_context import CallbackContext
from PIL import Image
from shared.constants import GCS_INGREDIENT_IMAGES_FOLDER

from utils.storage import upload_image_to_gcs


def before_agent_callback(callback_context: CallbackContext) -> None:
  """Uploads any inline images from the user turn to GCS before the agent runs."""  # noqa: E501
  logging.info("before_agent_callback")
  state = callback_context.state
  state["ingredient_images_folder"] = GCS_INGREDIENT_IMAGES_FOLDER
  state.setdefault("uploaded_images_gcs_uri", [])

  user_content = callback_context.user_content
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
      state.setdefault("uploaded_images_gcs_uri", []).append(gcs_uri)
      logging.info(
        f"Callback: Uploaded image saved to GCS at {gcs_uri} and state updated."
      )
