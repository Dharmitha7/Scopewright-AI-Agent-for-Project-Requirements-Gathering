"""Parse AG-UI-style SSE bodies from the chat stream endpoint."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class StreamEvent:
    event: str
    data: dict


def parse_sse(body: str) -> list[StreamEvent]:
    events: list[StreamEvent] = []
    event_name = "message"
    data_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
        elif line == "" and data_lines:
            raw = "\n".join(data_lines)
            events.append(StreamEvent(event=event_name, data=json.loads(raw) if raw else {}))
            data_lines = []
            event_name = "message"
    if data_lines:
        raw = "\n".join(data_lines)
        events.append(StreamEvent(event=event_name, data=json.loads(raw) if raw else {}))
    return events
