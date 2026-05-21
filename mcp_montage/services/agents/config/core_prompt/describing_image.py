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

"""A describing image agent configuration. (This is the core prompt and should not be modified.)"""  # noqa: E501

from typing import Any

describing_image_instruction: str = """\
Analyze the provided image and write a concise description of the image.
"""  # noqa: E501


describing_image_config: dict[str, Any] = {
  "agent_name": "describing_image",
  "model_config": {
    "system_instruction": describing_image_instruction,
    "temperature": 0.2,
  },
}
