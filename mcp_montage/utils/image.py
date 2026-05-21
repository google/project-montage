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

"""Image utilities."""

import io
from io import BytesIO
from pathlib import Path

from google.genai import types
from PIL import Image

from utils.storage import download_bytes_from_gcs


def get_image_bytes(image: Image.Image, desired_format: str = "PNG") -> bytes:
  image_bytes_io = BytesIO()
  image.save(image_bytes_io, format=desired_format)
  return image_bytes_io.getvalue()


def get_pil_image(image_bytes: bytes):
  return Image.open(BytesIO(image_bytes))


def get_mime_type_from_uri(uri: str):
  for name in reversed(uri.split("/")):
    name_split = name.split(".")
    if len(name_split) == 1:
      continue
    else:
      extension = name_split[-1].lower().strip()
      if extension in ["jpg", "jpeg"]:
        return "image/jpeg"
      elif extension == "png":
        return "image/png"
      elif extension == "webp":
        return "image/webp"
      elif extension == "gif":
        return "image/gif"
  return "image/png"


def convert_image_to_part(
  image: bytes | str | Image.Image,
  mime_type: str | None = None,
) -> types.Part:
  """Coerce supported image inputs into a Gemini content part."""
  data: bytes
  detected_mime: str | None = mime_type or "image/png"

  if isinstance(image, bytes):
    data = image
  elif isinstance(image, Image.Image):
    buffer = io.BytesIO()
    # Default to PNG to preserve alpha while avoiding additional deps
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
  elif isinstance(image, str):
    path = Path(image)
    data = (
      path.read_bytes() if path.exists() else download_bytes_from_gcs(image)
    )
    detected_mime = detected_mime or get_mime_type_from_uri(str(path))

  if not detected_mime:
    raise ValueError(
      "Unable to determine MIME type for the provided image. Specify `image_mime_type` explicitly."  # noqa: E501
    )

  return types.Part.from_bytes(data=data, mime_type=detected_mime)
