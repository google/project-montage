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

"""Utilities for calling Google APIs."""

from typing import Any

import google.auth
import google.auth.transport.requests
import httpx
from google.auth.credentials import Credentials
from tenacity import retry, stop_after_attempt, wait_exponential

from utils import log

logger = log.get_logger()


def get_auth_headers(url: str) -> dict[str, str]:
  """Get authorization headers for Google APIs."""
  if "localhost" in url or "127.0.0.1" in url:
    return {}

  try:
    creds, _ = google.auth.default()
    if isinstance(creds, Credentials) and not creds.valid:
      # Refresh the credentials if they are expired or not present
      auth_req = google.auth.transport.requests.Request()
      creds.refresh(auth_req)

      return {"Authorization": f"Bearer {creds.token}"}

    return {}
  except Exception as e:
    logger.error(f"Failed to get auth token: {e}")
    return {}


@retry(
  wait=wait_exponential(min=5, max=60, multiplier=2),
  stop=stop_after_attempt(3),
)
async def send_request_to_google_api(
  api_endpoint: str,
  data: dict[str, Any],
  method: str = "POST",
  headers: dict[str, str] | None = None,
) -> str:
  """Sends an HTTP request to a Google API endpoint.

  Args:
      api_endpoint: The URL of the Google API endpoint.
      data: Dictionary of data to send in the request body (for POST, PUT,
          etc.).
      method: The HTTP method to use (default: "POST").
      headers: (Optional) Dictionary of headers to send.

  Returns:
      The response from the Google API as a string.

  Raises:
      ValueError: If the request fails.
  """
  try:
    if headers is None:
      headers = {}

    auth_headers = get_auth_headers(api_endpoint)
    headers.update(auth_headers)
    headers.update({"Content-Type": "application/json"})

    async with httpx.AsyncClient(timeout=120.0) as client:
      response = await client.request(
        method=method,
        url=api_endpoint,
        headers=headers,
        json=data,
      )
      response.raise_for_status()

  except Exception as e:
    raise ValueError(f"Send Google API Error: {e}") from e

  return response.text
