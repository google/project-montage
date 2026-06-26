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

from dataclasses import dataclass, field
from typing import Annotated

from pydantic import Field
from shared.constants import VIEW_ENDPOINT

from schemas.voice import VoiceProfile


@dataclass
class VideoMetadata:
  """Metadata for a video includes its GCS URI and description."""

  gcs_uri: Annotated[str, Field(description="GCS URI of the video.")]
  duration_seconds: Annotated[
    float, Field(description="Duration of the video in seconds.")
  ]
  authenticated_url: Annotated[
    str, Field(description="URL of the video where user can view.")
  ] = field(init=False)

  def __post_init__(self):
    """Post-initialization to set default authenticated_url from gcs_uri."""
    gsc_uri_parsed = self.gcs_uri[5:]
    self.authenticated_url = VIEW_ENDPOINT + gsc_uri_parsed


@dataclass
class AudioMetadata:
  """Metadata for an audio asset stored in GCS."""

  gcs_uri: Annotated[str, Field(description="GCS URI of the audio file.")]
  duration_seconds: Annotated[
    float, Field(description="Duration of the audio in seconds.")
  ]
  refined_ass_content: Annotated[
    str | None,
    Field(
      description=(
        "Refined ASS subtitle content emitted when the voiceover refinement "
        "loop shortened one or more lines to fit their scene window. None "
        "when no refinement happened. When set, callers MUST pass this "
        "string -- not the original ASS -- to render_final_video so the "
        "burned-in subtitles stay in sync with the stitched voiceover."
      ),
    ),
  ] = None
  authenticated_url: Annotated[
    str, Field(description="URL of the audio where user can view.")
  ] = field(init=False)

  def __post_init__(self):
    """Post-initialization to set default authenticated_url from gcs_uri."""
    gsc_uri_parsed = self.gcs_uri[5:]
    self.authenticated_url = VIEW_ENDPOINT + gsc_uri_parsed


@dataclass
class NarrativeLine:
  """User-friendly narrative line parsed from ASS dialogue."""

  timestamp: Annotated[
    str,
    Field(
      description="Start timestamp of the narrative line in ASS time format."
    ),
  ]
  text: Annotated[
    str,
    Field(description="Plain readable text for the narrative line."),
  ]


@dataclass
class Narrative:
  """Narrative content in raw ASS and user-friendly readable formats."""

  ass_content: Annotated[
    str,
    Field(
      description="Generated narration subtitles in raw ASS format.",
    ),
  ]
  readable_content: Annotated[
    list[NarrativeLine],
    Field(
      description="Readable narrative lines with timestamp and plain text pairs.",  # noqa: E501
    ),
  ]
  voice_profile: Annotated[
    VoiceProfile | None,
    Field(
      description="Voice-casting selection chosen with the video/storyboard context. Pass this straight to generate_voiceover so it doesn't re-pick a voice blind. None when no profile was chosen.",  # noqa: E501
    ),
  ] = None
