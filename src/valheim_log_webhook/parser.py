"""Line-level Valheim event parser."""

from __future__ import annotations

import re

from .config import RuntimeConfig
from .events import EventType, NormalizedEvent, ParseMiss

JOIN_NAME_PATTERN = re.compile(r"Got character ZDOID from\s+(?P<name>[^:]+?)\s*:")
STEAM_ID_PATTERN = re.compile(r"(?P<steam_id>\d{17})")
RAID_PATTERN = re.compile(r"Random event set:\s*(?P<raid>.+)$")
DEATH_WITH_FROM_PATTERN = re.compile(
    r"Got character ZDOID from\s+(?P<name>[^:]+?)\s*:.*got status effect Dead"
)
DEATH_FALLBACK_PATTERN = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9_\- ]*)\s+got status effect Dead"
)


def parse_line(line: str, config: RuntimeConfig) -> NormalizedEvent | ParseMiss:
    """Parse one log line into a normalized event or parse miss.

    Parameters
    ----------
    line : str
        One Valheim log line.
    config : RuntimeConfig
        Runtime filter configuration.

    Returns
    -------
    NormalizedEvent | ParseMiss
        Parsed event for matching valid lines, otherwise a miss with reason.
    """
    if config.filter_online in line:
        return NormalizedEvent(event_type=EventType.SERVER_ONLINE, raw_line=line)

    if config.filter_offline in line:
        return NormalizedEvent(event_type=EventType.SERVER_OFFLINE, raw_line=line)

    if config.filter_death in line:
        steam_id = _extract_steam_id(line)
        death_name = _extract_death_player_name(line)
        if death_name is None and steam_id is None:
            return ParseMiss(line=line, reason="death_missing_identifiers")

        return NormalizedEvent(
            event_type=EventType.PLAYER_DEATH,
            raw_line=line,
            player_name=death_name,
            steam_id=steam_id,
        )

    if config.filter_join in line:
        join_match = JOIN_NAME_PATTERN.search(line)
        if join_match is None:
            return ParseMiss(line=line, reason="join_missing_player_name")

        steam_id = _extract_steam_id(line)
        return NormalizedEvent(
            event_type=EventType.PLAYER_JOIN,
            raw_line=line,
            player_name=join_match.group("name").strip(),
            steam_id=steam_id,
        )

    if config.filter_leave in line:
        steam_id = _extract_steam_id(line)
        if steam_id is None:
            return ParseMiss(line=line, reason="leave_missing_steam_id")

        return NormalizedEvent(
            event_type=EventType.PLAYER_LEAVE,
            raw_line=line,
            steam_id=steam_id,
        )

    if config.filter_raid in line:
        raid_match = RAID_PATTERN.search(line)
        if raid_match is None:
            return ParseMiss(line=line, reason="raid_missing_name")

        return NormalizedEvent(
            event_type=EventType.RAID_START,
            raw_line=line,
            raid_name=raid_match.group("raid").strip(),
        )

    return ParseMiss(line=line, reason="no_pattern_match")


def _extract_steam_id(line: str) -> str | None:
    """Extract a 17-digit Steam identifier from a log line.

    Parameters
    ----------
    line : str
        Input log line.

    Returns
    -------
    str | None
        Steam ID when found.
    """
    steam_match = STEAM_ID_PATTERN.search(line)
    if steam_match is None:
        return None
    return steam_match.group("steam_id")


def _extract_death_player_name(line: str) -> str | None:
    """Extract the player name for a death event line.

    Parameters
    ----------
    line : str
        Input log line.

    Returns
    -------
    str | None
        Player name when detectable.
    """
    match = DEATH_WITH_FROM_PATTERN.search(line)
    if match is not None:
        return match.group("name").strip()

    fallback_match = DEATH_FALLBACK_PATTERN.search(line)
    if fallback_match is not None:
        return fallback_match.group("name").strip()

    return None
