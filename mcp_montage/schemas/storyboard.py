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

"""Storyboard output schemas returned by the storyboard generation tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any

from pydantic import Field


def _coerce_duration(value: Any) -> int:
  """Coerces an LLM-provided scene duration into an int (defaults to 0)."""
  if isinstance(value, bool):
    return 0
  if isinstance(value, int):
    return value
  try:
    return int(str(value).strip())
  except (TypeError, ValueError):
    return 0


# The ffmpeg xfade filter names concatenate_videos accepts for a buffered
# transition, mirrored from ConcatenateVideosRequest.
KNOWN_XFADE_TRANSITIONS: frozenset[str] = frozenset(
  {
    "fade",
    "wipeleft",
    "wiperight",
    "wipeup",
    "wipedown",
    "slideleft",
    "slideright",
    "slideup",
    "slidedown",
    "circlecrop",
    "rectcrop",
    "distance",
    "fadeblack",
    "fadewhite",
    "radial",
    "smoothleft",
    "smoothright",
    "smoothup",
    "smoothdown",
    "circleopen",
    "circleclose",
    "vertopen",
    "vertclose",
    "horzopen",
    "horzclose",
    "dissolve",
    "pixelize",
    "diagtl",
    "diagtr",
    "diagbl",
    "diagbr",
    "hlslice",
    "hrslice",
    "vuslice",
    "vdslice",
    "hblur",
    "fadegrays",
    "wipetl",
    "wipetr",
    "wipebl",
    "wipebr",
    "squeezeh",
    "squeezev",
    "zoomin",
    "fadefast",
    "fadeslow",
    "hlwind",
    "hrwind",
    "vuwind",
    "vdwind",
    "coverleft",
    "coverright",
    "coverup",
    "coverdown",
    "revealleft",
    "revealright",
    "revealup",
    "revealdown",
  }
)

TRANSITION_BUFFER_SECONDS: float = 1.0


def _coerce_transition(value: Any) -> str:
  """Normalizes an LLM-provided transition name (defaults to 'fade').

  Falls back to 'fade' for any name that is not a known ffmpeg xfade
  filter, so an LLM-invented transition fails here instead of after N
  buffered Omni clips have already been generated for it.
  """
  name = str(value).strip().lower() if value is not None else ""
  if not name:
    return "fade"
  if name == "none" or name in KNOWN_XFADE_TRANSITIONS:
    return name
  return "fade"


def _buffer_for_transition(transition: str) -> float:
  """Seconds of extra footage each clip needs for this transition."""
  if transition == "none":
    return 0.0
  return TRANSITION_BUFFER_SECONDS


@dataclass
class SceneImage:
  """A reference image composited into a storyboard scene."""

  gcs_uri: Annotated[
    str, Field(description="GCS URI of the source or asset image.")
  ]
  image_description: Annotated[
    str,
    Field(description="Description of what the referenced image contains."),
  ] = ""


@dataclass
class StoryboardScene:
  """A single scene (short video clip) within a storyboard."""

  scene_id: Annotated[
    str, Field(description="A unique, creative name for the scene.")
  ]
  scene_duration: Annotated[
    int,
    Field(description="Duration of the scene in seconds (4, 6, or 8)."),
  ]
  visual_description: Annotated[
    str,
    Field(description="Detailed description of the scene's visuals."),
  ]
  scene_number: Annotated[
    str,
    Field(description="Sequential scene number starting at 1."),
  ] = ""
  how_to_calculate_total_duration: Annotated[
    str,
    Field(description="Running total duration calculation for the scene."),
  ] = ""
  base_images: Annotated[
    list[SceneImage],
    Field(description="Reference images composited into the scene."),
  ] = field(default_factory=list)


@dataclass
class Storyboard:
  """A full storyboard: global style plus an ordered list of scenes."""

  story_mood_and_tone: Annotated[
    str,
    Field(description="The visual style, mood, and emotional quality."),
  ]
  every_scene_style: Annotated[
    str,
    Field(description="The artistic style applied to every generated image."),
  ]
  storyboard: Annotated[
    list[StoryboardScene],
    Field(description="The ordered list of scenes."),
  ] = field(default_factory=list)
  scene_number: Annotated[
    str,
    Field(description="Top-level scene number emitted by the text variant."),
  ] = ""
  transition: Annotated[
    str,
    Field(
      description="Transition applied at every scene boundary (e.g. 'fade', 'none', 'dissolve', 'wipeleft')."  # noqa: E501
    ),
  ] = "fade"
  transition_buffer_seconds: Annotated[
    float,
    Field(
      description="Extra seconds each non-final clip must be generated with so the transition consumes buffer instead of real footage. Derived from `transition`; 0.0 only for 'none'. Pass to generate_videos_omni and concatenate_videos."  # noqa: E501
    ),
  ] = 0.0

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Storyboard:
    """Builds a Storyboard from the raw JSON dict produced by the LLM.

    Tolerates the two prompt shapes (text vs image variant) and coerces
    loosely-typed fields (e.g. string durations) into the schema types.

    Args:
      data: The parsed JSON object returned by the storyboard agent.

    Returns:
      A populated Storyboard instance.
    """
    scenes: list[StoryboardScene] = []
    for raw in data.get("storyboard", []):
      if not isinstance(raw, dict):
        continue
      base_images = [
        SceneImage(
          gcs_uri=str(img.get("gcs_uri", "")),
          image_description=str(img.get("image_description", "")),
        )
        for img in raw.get("base_images", [])
        if isinstance(img, dict)
      ]
      scenes.append(
        StoryboardScene(
          scene_id=str(raw.get("scene_id", "")),
          scene_duration=_coerce_duration(raw.get("scene_duration", 0)),
          visual_description=str(raw.get("visual_description", "")),
          scene_number=str(raw.get("scene_number", "")),
          how_to_calculate_total_duration=str(
            raw.get("how_to_calculate_total_duration", "")
          ),
          base_images=base_images,
        )
      )
    transition = _coerce_transition(data.get("transition"))
    return cls(
      story_mood_and_tone=str(data.get("story_mood_and_tone", "")),
      every_scene_style=str(data.get("every_scene_style", "")),
      storyboard=scenes,
      scene_number=str(data.get("scene_number", "")),
      transition=transition,
      transition_buffer_seconds=_buffer_for_transition(transition),
    )
