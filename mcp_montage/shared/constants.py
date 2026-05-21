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

"""Constants for MCP server."""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

# Environment variables
GOOGLE_GENAI_USE_VERTEXAI: bool = (
  os.getenv(
    "GOOGLE_GENAI_USE_VERTEXAI",
    "False",
  )
  == "True"
)
GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
GCS_INGREDIENT_IMAGES_FOLDER = os.environ.get(
  "GCS_INGREDIENT_IMAGES_FOLDER", ""
)
LOGGING_LEVEL = os.getenv(key="LOGGING_LEVEL", default="INFO")
LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "True").lower() == "true"
VIEW_ENDPOINT = os.getenv(
  key="VIEW_ENDPOINT", default="https://storage.cloud.google.com/"
)
