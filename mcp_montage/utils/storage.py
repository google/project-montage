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
import mimetypes
import os
import time
import uuid

from google.cloud import storage
from PIL import Image
from schemas.media import RawMediaItem
from shared.constants import GOOGLE_CLOUD_PROJECT

from utils import log

logger = log.get_logger()
storage_client = storage.Client(project=GOOGLE_CLOUD_PROJECT)


def _parse_gcs_uri(gcs_uri: str):
  if not gcs_uri.startswith("gs://"):
    raise ValueError("Expected a gs:// URI")
  parts = gcs_uri[5:].split("/", 1)
  bucket = parts[0]
  prefix = parts[1] if len(parts) > 1 else ""
  return bucket, prefix


def list_gcs_images(gcs_folder_uri: str) -> list[str]:
  bucket_name, prefix = _parse_gcs_uri(gcs_folder_uri)
  blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
  uris: list[str] = []
  for b in blobs:
    if b.name.endswith("/"):
      continue
    ext = os.path.splitext(b.name)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
      uris.append(f"gs://{bucket_name}/{b.name}")
  return uris


def upload_image_to_gcs(
  image: Image.Image,
  bucket_name: str,
  output_file_name: str,
  output_folder: str,
) -> str:
  """Uploads a PIL Image to Google Cloud Storage and returns the GCS URI."""
  image_bytes = io.BytesIO()
  image.save(image_bytes, format="PNG")
  image_bytes.seek(0)

  path = f"{output_folder}/{output_file_name}"
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(path)
  blob.upload_from_file(image_bytes, content_type="image/png")

  return f"gs://{bucket_name}/{path}"


def download_bytes_from_gcs(gcs_uri: str) -> bytes:
  """Downloads a file from Google Cloud Storage and returns it as bytes."""
  bucket_name, blob_name = _parse_gcs_uri(gcs_uri)
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(blob_name)
  image_bytes = blob.download_as_bytes()
  return image_bytes


def download_blob_to_file(gcs_uri: str, file_path: str) -> None:
  """Downloads a blob from GCS to a local file."""
  bucket_name, blob_name = _parse_gcs_uri(gcs_uri)
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(blob_name)
  blob.download_to_filename(file_path)


def upload_file_to_gcs(
  file_path: str,
  gcs_uri: str,
  content_type: str | None = None,
) -> str:
  """Uploads a local file to GCS."""
  bucket_name, blob_name = _parse_gcs_uri(gcs_uri)
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(blob_name)
  blob.upload_from_filename(file_path, content_type=content_type)
  return gcs_uri


def save_media_batch(
  media_items: list[RawMediaItem],
  output_dir: str | None = None,
  output_gcs_uri: str | None = None,
  file_prefix: str = "media",
) -> list[str]:
  """Saves a batch of media items either locally or to GCS.

  Args:
    media_items: List of RawMediaItem objects.
    output_dir: Local directory to save to (used if output_gcs_uri is None).
    output_gcs_uri: Optional GCS URI to upload to.
    file_prefix: Prefix for the filenames.

  Returns:
    List of saved file paths or GCS URIs.
  """
  if not media_items:
    logger.warning("No media items to save.")
    return []

  if output_gcs_uri:
    return _save_media_to_gcs(media_items, output_gcs_uri, file_prefix)
  elif output_dir:
    return _save_media_locally(media_items, output_dir, file_prefix)
  else:
    raise ValueError("Either output_dir or output_gcs_uri must be provided.")


def _save_media_to_gcs(
  media_items: list[RawMediaItem],
  output_gcs_uri: str,
  file_prefix: str,
) -> list[str]:
  uris = []
  bucket_name, prefix = _parse_gcs_uri(output_gcs_uri)
  bucket = storage_client.bucket(bucket_name)

  for n, item in enumerate(media_items):
    mime_type = item.mime_type
    ext = mimetypes.guess_extension(mime_type) or ""
    suffix = uuid.uuid4().hex[:8]
    blob_name = f"{file_prefix}_{n}_{suffix}{ext}"
    if prefix:
      blob_name = f"{prefix}/{blob_name}"
    blob = bucket.blob(blob_name)

    blob.upload_from_string(item.data, content_type=mime_type)

    gcs_path = f"gs://{bucket_name}/{blob_name}"
    logger.info(f"Media uploaded to {gcs_path}")
    uris.append(gcs_path)

  return uris


def _save_media_locally(
  media_items: list[RawMediaItem],
  output_dir: str,
  file_prefix: str,
) -> list[str]:
  paths = []

  timestamp_dir = os.path.join(output_dir, uuid.uuid4().hex[:8])
  while os.path.exists(timestamp_dir):
    time.sleep(1)
    timestamp_dir = os.path.join(output_dir, uuid.uuid4().hex[:8])
  os.makedirs(timestamp_dir, exist_ok=True)

  for n, item in enumerate(media_items):
    mime_type = item.mime_type
    ext = mimetypes.guess_extension(mime_type) or ""
    file_name = os.path.join(timestamp_dir, f"{file_prefix}_{n}{ext}")

    with open(file_name, "wb") as f:
      f.write(item.data)

    logger.info(f"Media saved to {file_name}")
    paths.append(file_name)

  return paths
