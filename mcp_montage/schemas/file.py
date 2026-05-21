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

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field
from shared.constants import VIEW_ENDPOINT


@dataclass
class FileMetadata:
  """Metadata for a file includes its GCS URI."""

  gcs_uri: Annotated[str, Field(description="GCS URI of the file.")]
  authenticated_url: Annotated[
    str, Field(description="URL of the file where user can view.")
  ] = Field(init=False)

  def __post_init__(self):
    """Post-initialization to set default authenticated_url from gcs_uri."""
    gsc_uri_parsed = self.gcs_uri[5:]
    self.authenticated_url = VIEW_ENDPOINT + gsc_uri_parsed
