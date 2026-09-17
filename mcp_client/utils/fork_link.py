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

"""The in-chat fork link: how it is written and where it points.

An after_agent_callback emits one of these at the end of each agent turn
(see utils/state.py). It is replayed unchanged into any fork made from
that session, still pointing at whatever session it was originally
emitted in -- forking from a replayed turn creates a sibling of the fork
being viewed, not a child of it, but keeps every historical turn forkable.
See docs/superpowers/specs/2026-08-07-in-chat-fork-link-design.md.
"""

from __future__ import annotations

from urllib.parse import urlencode

from google.adk.sessions.session import Session
from google.genai import types

FORK_LINK_PATH = "/conversations/fork"
FORK_LINK_LABEL = "📍Branch from this point"


def build_fork_link_text(
  *, app_name: str, user_id: str, session_id: str, event_id: str
) -> str:
  """Builds the markdown fork link shown at the end of an agent turn.

  The href is root-relative on purpose: Angular's URL sanitizer in the
  vendored dev-ui allows relative hrefs, so no public base URL needs to be
  configured for this to work behind IAP.
  """
  query = urlencode(
    {
      "app": app_name,
      "user": user_id,
      "session": session_id,
      "event": event_id,
    }
  )
  return f"[{FORK_LINK_LABEL}]({FORK_LINK_PATH}?{query})"


def build_fork_link_content(
  session: Session, invocation_id: str
) -> types.Content | None:
  """Builds the fork link for the turn that just finished, or None.

  `session.events[-1]` is the turn's real final event: the runner appends
  each event to the in-memory session before pulling the next one from the
  agent, so by the time after_agent_callback runs they are all present.
  Returns None when this turn produced no agent response at all -- either
  no events were added (events[-1] belongs to an earlier invocation), or
  the turn errored before the agent could reply (events[-1] is still the
  user's own message: ADK stamps that event with the *current*
  invocation_id -- see runners.py -- so the invocation_id check alone does
  not catch this case).
  """
  if not session.events:
    return None

  last_event = session.events[-1]
  if last_event.author == "user" or last_event.invocation_id != invocation_id:
    return None

  link = build_fork_link_text(
    app_name=session.app_name,
    user_id=session.user_id,
    session_id=session.id,
    event_id=last_event.id,
  )
  return types.Content(role="model", parts=[types.Part(text=link)])
