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
SIGNED_URL_EXPIRATION_MINUTES = int(
  os.getenv("SIGNED_URL_EXPIRATION_MINUTES", "60")
)

# Work around references:
# - https://stackoverflow.com/a/64245028
# - https://stackoverflow.com/a/70369296
credentials, project_id = google.auth.default()

ah_api = FastAPI()
app = FastAPI()
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

app.mount("/_ah", ah_api)


def get_storage_client():
  storage_client = storage.Client(project=GOOGLE_CLOUD_PROJECT)
  try:
    yield storage_client
  finally:
    storage_client.close()


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
  # 1. Parse the GCS URI
  # Remove prefix and split into bucket and object name
  path_parts = gcs_uri.split("/", 1)
  if len(path_parts) != 2:
    raise ValueError("URI must contain both a bucket and an object name.")

  bucket_name = path_parts[0]
  blob_name = path_parts[1]

  # 2. Get the bucket and blob
  bucket: storage.Bucket = storage_client.bucket(bucket_name)
  blob: storage.Blob = bucket.blob(blob_name)

  # 3. request credential
  r = requests.Request()
  credentials.refresh(r)  # type: ignore

  # 4. Generate the Signed URL
  url: str = blob.generate_signed_url(
    version="v4",
    expiration=timedelta(minutes=expiration_minutes),
    method="GET",
    service_account_email=credentials.service_account_email,  # type: ignore
    access_token=credentials.token,  # type: ignore
  )
  return url


@ah_api.get("/warmup")
def warmup():
  return ""


@app.get("/view")
def view_storage_object(
  uri: str,
  storage_client: Annotated[storage.Client, Depends(get_storage_client)],
):
  try:
    signed_url = generate_signed_url(
      storage_client, uri, SIGNED_URL_EXPIRATION_MINUTES
    )
    return RedirectResponse(url=signed_url)

  except ValueError as e:
    # Catch specific validation errors (e.g. malformed URI)
    raise HTTPException(status_code=400, detail=str(e)) from e

  except Exception as e:
    # Catch unexpected server errors
    logging.error(e)
    raise HTTPException(status_code=500, detail="Internal Server Error") from e
