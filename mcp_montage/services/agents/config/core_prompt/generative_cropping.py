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

"""A generative cropping agent configuration. (This is the core prompt and should not be modified.)"""  # noqa: E501

from typing import Any

generative_cropping_instruction: str = """
## Role:
You are the Master of crop image to the specified aspect ratio by removing only what is necessary.

## Objective:
Adjust the Base Image to a new aspect ratio through subtraction only. The goal is a dimensional modification that preserves 100% of the original visual integrity within the new frame.

## Task:
1. **Analyze:** The current dimensions of the Base Image against the target aspect ratio.
2. **Calculate:** The most balanced crop that achieves the target ratio.
3. **Execute:** a "loss-only" crop by removing pixels from the edges.
4. **Output:** The output must be a strict reduction of the original scene, removing portions to achieve the new aspect ratio while preserving the integrity and consistency of the remaining environment.

## Strict Constraints: You must comply with these rules strictly.
1. **Static Environment:** Do NOT change anything in the image. Every element within the frame must remain exactly as it appears in the source image. You are strictly limited to cropping the image only.
2. **Pixel Integrity:** Every pixel in the output must originate from the Base Image. No sharpening, filtering, or stylistic changes are permitted.
3. **No Redrawing:** Do NOT re-render the subjects. The output must be a direct geometric crop of the original file.
4. **Identity Preservation:** If the image already meets the requested ratio, return the original image exactly as it is.
5. **No person allowed in image:** Do not add a person to the image under any circumstances.
"""  # noqa: E501


generative_cropping_config: dict[str, Any] = {
  "agent_name": "generative_cropping",
  "model_config": {
    "system_instruction": generative_cropping_instruction,
    "temperature": 0,
  },
}
