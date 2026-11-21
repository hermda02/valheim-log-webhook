"""Discord routing and payload formatting for normalized events."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from .config import RuntimeConfig
from .events import EventType, NormalizedEvent

LOGGER = logging.getLogger(__name__)


class DiscordChannel(StrEnum):
    """Logical Discord webhook channels."""

    DEBUG = "debug"
    LOG = "log"
    PLAYERS = "players"


@dataclass(frozen=True)
class OutboundWebhook:
    """Prepared webhook request payload.

    Parameters
    ----------
    event_type : EventType
        Event that generated this webhook.
    channel : DiscordChannel
        Mapped Discord channel group.
    url : str
        Target Discord webhook URL.
    payload : dict[str, str]
        JSON body for Discord webhook endpoint.
    """

    event_type: EventType
    channel: DiscordChannel
    url: str
    payload: dict[str, str]


def route_event_to_webhook(
    event: NormalizedEvent, config: RuntimeConfig
) -> OutboundWebhook | None:
    """Map one event to its Discord target and payload.

    Parameters
    ----------
    event : NormalizedEvent
        Parsed normalized event.
    config : RuntimeConfig
        Runtime configuration with webhook settings.

    Returns
    -------
    OutboundWebhook | None
        Prepared request when routing succeeds; otherwise ``None``.
    """
    channel = _channel_for_event(event.event_type)
    url = _url_for_channel(channel=channel, config=config)

    if url is None:
        LOGGER.error(
            "Webhook URL not configured for channel=%s event_type=%s",
            channel,
            event.event_type,
        )
        return None

    if not _is_valid_webhook_url(url):
        LOGGER.error(
            "Webhook URL invalid for channel=%s event_type=%s",
            channel,
            event.event_type,
        )
        return None

    return OutboundWebhook(
        event_type=event.event_type,
        channel=channel,
        url=url,
        payload=_build_payload(event),
    )


def _channel_for_event(event_type: EventType) -> DiscordChannel:
    """Resolve logical Discord channel for an event type."""
    mapping = {
        EventType.SERVER_ONLINE: DiscordChannel.LOG,
        EventType.SERVER_OFFLINE: DiscordChannel.LOG,
        EventType.PLAYER_JOIN: DiscordChannel.PLAYERS,
        EventType.PLAYER_LEAVE: DiscordChannel.PLAYERS,
        EventType.RAID_START: DiscordChannel.PLAYERS,
        EventType.PLAYER_DEATH: DiscordChannel.PLAYERS,
    }
    return mapping[event_type]


def _url_for_channel(channel: DiscordChannel, config: RuntimeConfig) -> str | None:
    """Resolve webhook URL from configuration for a channel."""
    if channel == DiscordChannel.DEBUG:
        return config.discord_webhook_debug
    if channel == DiscordChannel.LOG:
        return config.discord_webhook_log
    return config.discord_webhook_players


def _build_payload(event: NormalizedEvent) -> dict[str, str]:
    """Build a stable Discord message payload for one event."""
    content = {
        EventType.SERVER_ONLINE: "[ONLINE] Valheim server is online.",
        EventType.SERVER_OFFLINE: "[OFFLINE] Valheim server went offline.",
        EventType.PLAYER_JOIN: f"[JOIN] {event.player_name or 'Unknown player'} joined the realm.",
        EventType.PLAYER_LEAVE: (
            f"[LEAVE] {event.player_name or event.steam_id or 'Unknown player'} left the realm."
        ),
        EventType.RAID_START: f"[RAID] Raid started: {event.raid_name or 'Unknown raid'}.",
        EventType.PLAYER_DEATH: f"[DEATH] {event.player_name or 'Unknown player'} has died.",
    }[event.event_type]

    return {
        "username": "Hugin",
        "content": content,
    }


def _is_valid_webhook_url(url: str) -> bool:
    """Validate webhook URL shape."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    if parsed.netloc == "":
        return False
    return parsed.path.startswith("/api/webhooks/")
