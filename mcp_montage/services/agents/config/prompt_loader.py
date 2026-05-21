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

"""Loader for specific prompt files."""

from pathlib import Path

_specific_prompt_dir = Path(__file__).parent / "specific_prompt"

with open(
  _specific_prompt_dir / "image_constraints_prompt.md", encoding="utf-8"
) as _f:
  generate_image_constraints_prompt = _f.read()

with open(
  _specific_prompt_dir / "image_constraints_nanobanana_prompt.md",
  encoding="utf-8",
) as _f:
  generate_image_constraints_nanobanana_prompt = _f.read()

with open(
  _specific_prompt_dir / "video_constraints_prompt.md", encoding="utf-8"
) as _f:
  video_constraints_prompt = _f.read()

with open(
  _specific_prompt_dir / "storyboard_constraints_prompt.md", encoding="utf-8"
) as _f:
  image_to_storyboard_constraints_prompt = _f.read()
