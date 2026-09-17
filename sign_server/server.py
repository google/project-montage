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

import logging
import os
from datetime import timedelta
from functools import lru_cache
from typing import Annotated

import google.auth
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.auth.transport import requests
from google.cloud import storage
from starlette.responses import RedirectResponse

load_dotenv()

# Configuration from environment variables
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
# The only bucket this server signs objects for. The service is public, so
# without this restriction it would sign any object its identity can read.
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
SIGNED_URL_EXPIRATION_MINUTES = int(
  os.getenv("SIGNED_URL_EXPIRATION_MINUTES", "60")
)

app = FastAPI()
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_credentials():
  """Loads Application Default Credentials on first use, not at import.

  Work around references:
  - https://stackoverflow.com/a/64245028
  - https://stackoverflow.com/a/70369296
  """
  credentials, _ = google.auth.default()
  return credentials


def get_storage_client():
  storage_client = storage.Client(project=GOOGLE_CLOUD_PROJECT)
  try:
    yield storage_client
  finally:
    storage_client.close()


def parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
  """Splits '<bucket>/<object>' into its bucket and object names."""
  path_parts = gcs_uri.split("/", 1)
  if len(path_parts) != 2 or not path_parts[0] or not path_parts[1]:
    raise ValueError("URI must contain both a bucket and an object name.")
  return path_parts[0], path_parts[1]


def generate_signed_url(
  storage_client: storage.Client, gcs_uri: str, expiration_minutes: int = 60
) -> str:
  """
  Generates a V4 Signed URL for a Google Cloud Storage blob.

  Args:
      gcs_uri (str): The GCS URI (e.g., 'bucket-name/path/to/object')
      expiration_minutes (int): URL expiration time in minutes.

  Returns:
      str: The signed URL.
  """
  bucket_name, blob_name = parse_gcs_uri(gcs_uri)

  bucket: storage.Bucket = storage_client.bucket(bucket_name)
  blob: storage.Blob = bucket.blob(blob_name)

  # Refresh to obtain an access token for IAM-based signing.
  credentials = get_credentials()
  credentials.refresh(requests.Request())  # type: ignore

  url: str = blob.generate_signed_url(
    version="v4",
    expiration=timedelta(minutes=expiration_minutes),
    method="GET",
    service_account_email=credentials.service_account_email,  # type: ignore
    access_token=credentials.token,  # type: ignore
  )
  return url


@app.get("/view")
def view_storage_object(
  uri: str,
  storage_client: Annotated[storage.Client, Depends(get_storage_client)],
):
  if not GCS_BUCKET_NAME:
    logging.error("GCS_BUCKET_NAME is not configured; refusing to sign.")
    raise HTTPException(status_code=500, detail="Internal Server Error")

  try:
    bucket_name, _ = parse_gcs_uri(uri)
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e)) from e

  if bucket_name != GCS_BUCKET_NAME:
    raise HTTPException(status_code=403, detail="Bucket is not allowed.")

  try:
    signed_url = generate_signed_url(
      storage_client, uri, SIGNED_URL_EXPIRATION_MINUTES
    )
    return RedirectResponse(url=signed_url)

  except Exception as e:
    # Catch unexpected server errors
    logging.error(e)
    raise HTTPException(status_code=500, detail="Internal Server Error") from e
