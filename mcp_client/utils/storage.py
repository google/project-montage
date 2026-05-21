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

"""Storage utils for handling image uploads and downloads to Google Cloud Storage."""  # noqa: E501

import io

from google.cloud import storage
from PIL import Image
from shared.constants import GCS_BUCKET_NAME

storage_client = storage.Client()


def upload_image_to_gcs(
  image: Image.Image,
  output_file_name: str,
  output_folder: str,
) -> str:
  """Uploads a PIL Image to Google Cloud Storage and returns the GCS URI."""
  image_bytes = io.BytesIO()
  image.save(image_bytes, format="PNG")
  image_bytes.seek(0)

  path = f"{output_folder}/{output_file_name}"
  bucket = storage_client.bucket(GCS_BUCKET_NAME)
  blob = bucket.blob(path)
  blob.upload_from_file(image_bytes, content_type="image/png")

  return f"gs://{GCS_BUCKET_NAME}/{path}"
