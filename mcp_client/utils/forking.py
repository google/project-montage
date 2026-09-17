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

"""Core logic for forking an ADK session: id lineage, state sanitizing,
and event replay. See docs/superpowers/specs/
2026-08-06-conversation-forking-design.md."""

from __future__ import annotations

import random
import string
import time
from typing import Any

from google.adk.events.event import Event
from google.adk.sessions.base_session_service import BaseSessionService

_FORK_MARKER = "--fork-"
_RAND_ALPHABET = string.ascii_lowercase + string.digits
_RAND_LENGTH = 6


def derive_root_id(session_id: str) -> str:
  """Returns the root session id, stripping from the first fork marker."""
  marker_index = session_id.find(_FORK_MARKER)
  if marker_index == -1:
    return session_id
  return session_id[:marker_index]


def generate_fork_session_id(root_id: str) -> str:
  """Generates a collision-resistant forked session id under root_id."""
  unix_ms = int(time.time() * 1000)
  rand6 = "".join(random.choices(_RAND_ALPHABET, k=_RAND_LENGTH))
  return f"{root_id}{_FORK_MARKER}{unix_ms}-{rand6}"


_SHARED_STATE_PREFIXES = ("app:", "user:")


def strip_shared_state_prefixes(state_delta: dict[str, Any]) -> dict[str, Any]:
  """Drops app:/user:-scoped keys so a replayed delta can only affect the
  forked session, never shared app/user state (see spec's "Replay and
  state" section)."""
  return {
    key: value
    for key, value in state_delta.items()
    if not key.startswith(_SHARED_STATE_PREFIXES)
  }


class SessionNotFoundError(LookupError):
  """Raised when the source session for a fork does not exist."""


class EventNotFoundError(LookupError):
  """Raised when the requested cut-point event id is not in the source
  session's event list."""


def _find_event_index(events: list[Event], event_id: str) -> int | None:
  for index, event in enumerate(events):
    if event.id == event_id:
      return index
  return None


async def perform_fork(
  service: BaseSessionService,
  *,
  app_name: str,
  user_id: str,
  session_id: str,
  up_to_event_id: str,
) -> str:
  """Forks `session_id` at `up_to_event_id`, returning the new session id.

  Replays events[:cut+1] from the source into a freshly created session via
  `append_event` -- the same mechanism ADK's own CreateSessionRequest.events
  handler uses. Never mutates the source session.
  """
  source = await service.get_session(
    app_name=app_name, user_id=user_id, session_id=session_id
  )
  if source is None:
    raise SessionNotFoundError(session_id)

  cut_index = _find_event_index(source.events, up_to_event_id)
  if cut_index is None:
    raise EventNotFoundError(up_to_event_id)

  root_id = derive_root_id(source.id)
  new_session_id = generate_fork_session_id(root_id)
  lineage_state = {
    "forked_from_session_id": source.id,
    "forked_from_event_id": up_to_event_id,
    "forked_at": int(time.time()),
  }
  new_session = await service.create_session(
    app_name=app_name,
    user_id=user_id,
    session_id=new_session_id,
    state=lineage_state,
  )

  for event in source.events[: cut_index + 1]:
    # Fork-link events are replayed like any other event, unchanged. Each
    # still carries the session id it was originally emitted in, so
    # clicking one later forks that ANCESTOR session (a sibling of this
    # fork), not this fork itself -- an accepted tradeoff that keeps every
    # historical turn forkable instead of only turns created after
    # entering a fork.
    # append_event mutates the event it's given (trims temp: keys), so copy
    # first to guarantee the source session's events are never touched.
    replay_event = event.model_copy(deep=True)
    replay_event.actions.state_delta = strip_shared_state_prefixes(
      replay_event.actions.state_delta
    )
    await service.append_event(session=new_session, event=replay_event)

  return new_session_id
