"""Application-level event processing loop."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from dataclasses import replace
from collections.abc import Callable, Iterable

from .config import RuntimeConfig
from .events import EventType, NormalizedEvent, ParseMiss
from .maintenance import BackupCoordinator
from .pipeline import parse_stream
from .routing import route_event_to_webhook
from .webhook import send_with_retry

LOGGER = logging.getLogger(__name__)

type ParseMissFn = Callable[[ParseMiss], None]


def process_lines(
    lines: Iterable[str],
    config: RuntimeConfig,
    on_parse_miss: ParseMissFn,
    *,
    backup_coordinator: BackupCoordinator | None = None,
) -> None:
    """Process raw log lines into routed webhook deliveries.

    Parameters
    ----------
    lines : Iterable[str]
        Raw incoming log stream.
    config : RuntimeConfig
        Runtime configuration.
    on_parse_miss : ParseMissFn
        Callback invoked for non-emitting parse outcomes.
    """
    known_player_names = _load_player_name_map(config.player_map_file_path)
    connected_players: set[str] = set()

    for event in parse_stream(lines, config, on_parse_miss=on_parse_miss):
        event = _enrich_player_name(event, known_player_names)

        if _is_duplicate_join(event, connected_players):
            LOGGER.debug(
                "suppressed_join_event reason=already_connected steam_id=%s player_name=%s",
                event.steam_id,
                event.player_name,
            )
            continue

        map_updated = _track_player_presence(event, known_player_names, connected_players)
        if map_updated:
            _persist_player_name_map(config.player_map_file_path, known_player_names)

        if _should_suppress_offline(event, backup_coordinator):
            LOGGER.info("suppressed_offline_event reason=backup_window")
            continue

        _deliver_event(event, config)


def send_scheduled_offline_alert(config: RuntimeConfig) -> None:
    """Emit an offline alert from post-backup health-check failure.

    Parameters
    ----------
    config : RuntimeConfig
        Runtime configuration.
    """
    _deliver_event(
        NormalizedEvent(
            event_type=EventType.SERVER_OFFLINE,
            raw_line="post_backup_healthcheck_failure",
        ),
        config,
    )


def _should_suppress_offline(
    event: NormalizedEvent,
    backup_coordinator: BackupCoordinator | None,
) -> bool:
    """Return whether an offline event should be suppressed."""
    if backup_coordinator is None:
        return False
    if event.event_type != EventType.SERVER_OFFLINE:
        return False
    return backup_coordinator.suppression_active()


def _deliver_event(event: NormalizedEvent, config: RuntimeConfig) -> None:
    """Route and deliver one normalized event."""
    outbound = route_event_to_webhook(event, config)
    if outbound is None:
        return

    result = send_with_retry(
        outbound,
        timeout_seconds=config.webhook_timeout_seconds,
        retry_delay_seconds=config.webhook_retry_delay_seconds,
    )
    if result.success:
        LOGGER.info(
            "webhook_sent event_type=%s channel=%s status=%s attempts=%s",
            outbound.event_type,
            outbound.channel,
            result.status_code,
            result.attempts,
        )


def _enrich_player_name(
    event: NormalizedEvent,
    known_player_names: dict[str, str],
) -> NormalizedEvent:
    """Backfill player names from known Steam ID mappings."""
    if event.player_name is not None:
        return event
    if event.steam_id is None:
        return event

    known_name = known_player_names.get(event.steam_id)
    if known_name is None:
        return event

    return replace(event, player_name=known_name)


def _is_duplicate_join(event: NormalizedEvent, connected_players: set[str]) -> bool:
    """Return whether a player-join event is a duplicate for a connected player."""
    if event.event_type != EventType.PLAYER_JOIN:
        return False

    player_key = _player_key(event)
    if player_key is None:
        return False

    return player_key in connected_players


def _track_player_presence(
    event: NormalizedEvent,
    known_player_names: dict[str, str],
    connected_players: set[str],
) -> bool:
    """Track connected players and Steam ID to player-name mappings."""
    map_updated = False
    if event.steam_id is not None and event.player_name is not None:
        previous_name = known_player_names.get(event.steam_id)
        if previous_name != event.player_name:
            known_player_names[event.steam_id] = event.player_name
            map_updated = True

    player_key = _player_key(event)
    if player_key is None:
        return map_updated

    if event.event_type == EventType.PLAYER_JOIN:
        connected_players.add(player_key)
        return map_updated
    if event.event_type == EventType.PLAYER_LEAVE:
        connected_players.discard(player_key)

    return map_updated


def _player_key(event: NormalizedEvent) -> str | None:
    """Build a stable player identity key for presence tracking."""
    if event.steam_id is not None:
        return f"steam:{event.steam_id}"
    if event.player_name is not None:
        return f"name:{event.player_name}"
    return None


def _load_player_name_map(map_file_path: str | None) -> dict[str, str]:
    """Load persisted Steam ID to player-name mappings from disk."""
    if map_file_path is None:
        return {}

    map_path = Path(map_file_path)
    if not map_path.exists():
        return {}

    try:
        raw_data = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("player_map_load_failed path=%s error=%s", map_path, exc)
        return {}

    if not isinstance(raw_data, dict):
        LOGGER.warning("player_map_invalid_format path=%s", map_path)
        return {}

    return {
        steam_id: player_name
        for steam_id, player_name in raw_data.items()
        if isinstance(steam_id, str) and isinstance(player_name, str)
    }


def _persist_player_name_map(
    map_file_path: str | None,
    known_player_names: dict[str, str],
) -> None:
    """Persist Steam ID to player-name mappings to disk."""
    if map_file_path is None:
        return

    map_path = Path(map_file_path)
    try:
        map_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = map_path.with_suffix(f"{map_path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(known_player_names, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(map_path)
    except OSError as exc:
        LOGGER.error("player_map_persist_failed path=%s error=%s", map_path, exc)
