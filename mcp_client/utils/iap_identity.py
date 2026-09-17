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

"""Derives a friendly display name from Google IAP's authenticated-user header.

Cloud Run's built-in IAP integration forwards `X-Goog-Authenticated-User-Email`
(format `accounts.google.com:user@example.com`) once a request is authenticated.
Locally (no IAP in front) the header is absent, so callers fall back to a
manually-entered display name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
  email: str | None
  display_name: str | None


def parse_iap_identity(header_value: str | None) -> Identity:
  if not header_value or not header_value.strip():
    return Identity(email=None, display_name=None)

  value = header_value.strip()
  email = value.split(":", 1)[1] if ":" in value else value
  email = email.strip()
  if not email or "@" not in email:
    return Identity(email=None, display_name=None)

  local_part = email.split("@", 1)[0]
  words = [w for w in re.split(r"[._+]+", local_part) if w]
  display_name = " ".join(w.capitalize() for w in words) or None
  return Identity(email=email, display_name=display_name)
