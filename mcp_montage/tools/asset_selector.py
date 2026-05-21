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

"""Select assets based on text input tool for MCP server."""

from __future__ import annotations

from logging import Logger

from mcp.server.fastmcp import FastMCP
from schemas.image import ImageMetadata, SelectAssetRequest
from services.agents.factory import AgentFactory
from services.agents.text_agent import GeminiAgent
from utils.storage import list_gcs_images


def register_asset_selector_tool(
  mcp: FastMCP, logger: Logger, bucket_name: str
) -> None:
  """Register the asset_selector tool on the provided MCP server."""  # noqa: E501

  @mcp.tool()
  async def select_asset(
    request: SelectAssetRequest,
  ) -> list[ImageMetadata]:
    """
    Select the most suitable asset image based on the provided user context and image context using gemini.

    Args:
      requests: SelectAssetRequest objects.
                Each object contains:
                - assets_folder: GCS folder URI containing various asset images.
                - images_context: List of GCS URIs of user-provided images.
                - text_requirement (string): Text describing the user requirements.

     Returns:
      A ImageMetadata object list.
      Each object contains:
      - gcs_uri: GCS URI of the selected asset image.
      - image_description: String describing what the image looks like (character appearance, style, etc.).
    """  # noqa: E501
    asset_selector_agent: GeminiAgent = AgentFactory.create_text_agent(
      agent_name="asset_selector"
    )
    assets = await asset_selector_agent.generate_json_content_async(
      contents=request.to_contents()
    )

    # Logic to filter out selected assets that do not exist in the GCS folder
    valid_assets_list = list_gcs_images(request.assets_folder)
    valid_assets_set = set(valid_assets_list)

    try:
      selected_image_metadata_list = []
      for selected_image in assets["selected_assets"]:
        gcs_uri = selected_image["gcs_uri"]
        if gcs_uri not in valid_assets_set:
          logger.warning(
            f"Selected asset {gcs_uri} not found in {request.assets_folder}."
          )
          continue
        selected_image_metadata_list.append(
          await ImageMetadata.create(
            gcs_uri=gcs_uri,
            image_description=selected_image["image_description"],
          )
        )
    except Exception as err:
      logger.error(err)
      raise err

    return selected_image_metadata_list
