"""Event data models used by log parsing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EventType(StrEnum):
    """Supported normalized event types for v1."""

    SERVER_ONLINE = "server_online"
    SERVER_OFFLINE = "server_offline"
    PLAYER_JOIN = "player_join"
    PLAYER_LEAVE = "player_leave"
    RAID_START = "raid_start"
    PLAYER_DEATH = "player_death"


@dataclass(frozen=True)
class NormalizedEvent:
    """A normalized event emitted from a matching Valheim log line.

    Parameters
    ----------
    event_type : EventType
        Canonical event type.
    raw_line : str
        Original log line.
    player_name : str | None
        Player character name when applicable.
    steam_id : str | None
        Steam identifier when applicable.
    raid_name : str | None
        Raid name when applicable.
    """

    event_type: EventType
    raw_line: str
    player_name: str | None = None
    steam_id: str | None = None
    raid_name: str | None = None


@dataclass(frozen=True)
class ParseMiss:
    """A non-emitting parse outcome with an observable reason.

    Parameters
    ----------
    line : str
        Original input line.
    reason : str
        Machine-readable miss reason.
    """

    line: str
    reason: str
