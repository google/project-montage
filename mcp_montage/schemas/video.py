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

from schemas.file import FileMetadata


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
class VideoGenerationRequest:
  gcs_uri: Annotated[
    str,
    Field(description="GCS URI of the first-frame image used for the video."),
  ]
  prompt: Annotated[
    str,
    Field(description="Optional text prompt describing a video."),
  ] = ""
  aspect_ratio: Annotated[
    str,
    Field(
      description="Aspect ratio of output video (e.g., '16:9', '9:16', '1:1'). Default to 16:9"  # noqa: E501
    ),
  ] = "16:9"
  duration_seconds: Annotated[
    int,
    Field(
      description="Desired duration of the generated video in seconds. Must be 4, 6, or 8."  # noqa: E501
    ),
  ] = 6


@dataclass
class ConcatenateVideosRequest:
  video_gcs_uris: Annotated[
    list[str],
    Field(
      description="Sequential list of GCS URIs for video paths. The first video is the first scene, the second video is the second scene, and so on."  # noqa: E501
    ),
  ]
  transition: Annotated[
    str,
    Field(
      description="""Type of transition effect between videos. Default to 'fade'. If you don't want any transition, use 'none'. Pick one from the following:
'none'
'fade'
'wipeleft'
'wiperight'
'wipeup'
'wipedown'
'slideleft'
'slideright'
'slideup'
'slidedown'
'circlecrop'
'rectcrop'
'distance'
'fadeblack'
'fadewhite'
'radial'
'smoothleft'
'smoothright'
'smoothup'
'smoothdown'
'circleopen'
'circleclose'
'vertopen'
'vertclose'
'horzopen'
'horzclose'
'dissolve'
'pixelize'
'diagtl'
'diagtr'
'diagbl'
'diagbr'
'hlslice'
'hrslice'
'vuslice'
'vdslice'
'hblur'
'fadegrays'
'wipetl'
'wipetr'
'wipebl'
'wipebr'
'squeezeh'
'squeezev'
'zoomin'
'fadefast'
'fadeslow'
'hlwind'
'hrwind'
'vuwind'
'vdwind'
'coverleft'
'coverright'
'coverup'
'coverdown'
'revealleft'
'revealright'
'revealup'
'revealdown'"""  # noqa: E501
    ),
  ] = "fade"


@dataclass
class GenerateBGMAndMergeRequest:
  video_gcs_uri: Annotated[
    str, Field(description="GCS URI of the video to add audio to.")
  ]
  prompt: Annotated[
    str, Field(description="Optional text prompt for music generation.")
  ] = ""


@dataclass
class GenerateSceneNarrativesRequest:
  video_gcs_uri: Annotated[
    str, Field(description="GCS URI of the video to generate narration for.")
  ]
  prompt: Annotated[
    str,
    Field(
      description="Optional text prompt guiding the narration style and content."  # noqa: E501
    ),
  ] = ""


@dataclass
class GenerateSceneNarrativesResponse:
  """Response for scene narrative generation, including SRT and subtitled video."""  # noqa: E501

  srt_file: Annotated[
    FileMetadata,
    Field(
      description="Metadata for the generated SRT file including gcs uri and authenticated url which a user can access.",  # noqa: E501
    ),
  ]
  video: Annotated[
    VideoMetadata,
    Field(
      description="Metadata for the video with embedded subtitles including gcs uri and authenticated url which a user can access.",  # noqa: E501
    ),
  ]
