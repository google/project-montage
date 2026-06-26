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

from dataclasses import dataclass, field
from typing import Annotated

from google.genai import types
from pydantic import Field
from shared.constants import VIEW_ENDPOINT
from utils.image import convert_image_to_part


@dataclass
class ImageMetadata:
  """Metadata for an image includes its GCS URI and description."""

  gcs_uri: Annotated[str, Field(description="GCS URI of the image.")]
  authenticated_url: Annotated[
    str, Field(description="URL of the image where user can view.")
  ] = field(init=False)
  image_description: Annotated[
    str,
    Field(
      description="""Description of what the image looks like(character appearance, style, etc.)."""  # noqa: E501
    ),
  ] = ""

  def __post_init__(self):
    """Post-initialization to set default authenticated_url from gcs_uri."""
    gsc_uri_parsed = self.gcs_uri[5:]
    self.authenticated_url = VIEW_ENDPOINT + gsc_uri_parsed

  @classmethod
  async def create(
    cls, gcs_uri: str, image_description: str = ""
  ) -> "ImageMetadata":
    """
    Async factory method to instantiate the class and populate
    missing data asynchronously.
    """
    # Create the instance (runs __post_init__ for the URL logic)
    instance = cls(gcs_uri=gcs_uri, image_description=image_description)

    # If description is missing, await the async generation
    if not instance.image_description:
      instance.image_description = await instance._get_image_description()

    return instance

  async def _get_image_description(self) -> str:
    """Get image description using LLM agent"""
    from services.agents.factory import AgentFactory

    describing_image_agent = AgentFactory.create_text_agent(
      agent_name="describing_image",
    )
    image_description = await describing_image_agent.generate_content_async(
      contents=[convert_image_to_part(image=self.gcs_uri)]
    )
    return image_description

  def to_contents(self) -> list[types.Part]:
    """Converts the image metadata to a formatted string for prompts."""
    return [
      types.Part.from_text(
        text=f"### Image URI: {self.gcs_uri}, Image Part: "  # noqa: E501
      ),
      convert_image_to_part(image=self.gcs_uri),
    ]
