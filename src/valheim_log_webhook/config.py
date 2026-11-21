"""Runtime configuration for the sidecar."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime settings loaded from environment variables.

    Parameters
    ----------
    container_name : str
        Name of the running Valheim server container to follow.
    reconnect_delay_seconds : float
        Delay between log stream reconnect attempts.
    filter_online : str
        Substring that identifies server-online lines.
    filter_offline : str
        Substring that identifies server-offline lines.
    filter_join : str
        Substring that identifies player-join lines.
    filter_leave : str
        Substring that identifies player-leave lines.
    filter_raid : str
        Substring that identifies raid-start lines.
    filter_death : str
        Substring that identifies player-death lines.
    discord_webhook_debug : str | None
        Discord webhook URL for debug/operator messages.
    discord_webhook_log : str | None
        Discord webhook URL for lifecycle log messages.
    discord_webhook_players : str | None
        Discord webhook URL for player-facing messages.
    webhook_timeout_seconds : float
        Timeout in seconds for outbound webhook requests.
    webhook_retry_delay_seconds : float
        Delay before one retry on transient send failures.
    timezone_name : str
        IANA timezone used for backup schedule interpretation.
    backups_enabled : bool
        Whether backup-aware suppression and post-backup health checks are enabled.
    backups_cron : str | None
        Backup cron expression, expected as five fields.
    backup_grace_minutes : int
        Minutes after backup start before a down message is allowed.
    backup_suppress_before_minutes : int
        Minutes before backup start where down messages are suppressed.
    backup_suppress_after_minutes : int
        Minutes after backup start where down messages are suppressed.
    backup_healthcheck_interval_seconds : int
        Poll interval for scheduled post-backup health checks.
    healthcheck_udp_port : int
        UDP port used to verify Valheim responsiveness.
    """

    container_name: str
    reconnect_delay_seconds: float
    filter_online: str
    filter_offline: str
    filter_join: str
    filter_leave: str
    filter_raid: str
    filter_death: str
    discord_webhook_debug: str | None = None
    discord_webhook_log: str | None = None
    discord_webhook_players: str | None = None
    webhook_timeout_seconds: float = 5.0
    webhook_retry_delay_seconds: float = 1.0
    timezone_name: str = "UTC"
    backups_enabled: bool = False
    backups_cron: str | None = None
    backup_grace_minutes: int = 25
    backup_suppress_before_minutes: int = 5
    backup_suppress_after_minutes: int = 25
    backup_healthcheck_interval_seconds: int = 30
    healthcheck_udp_port: int = 2456

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        """Create runtime configuration from process environment.

        Returns
        -------
        RuntimeConfig
            Parsed immutable runtime configuration.
        """
        return cls(
            container_name=os.getenv("VALHEIM_CONTAINER_NAME", "valheim-server"),
            reconnect_delay_seconds=float(
                os.getenv("LOG_RECONNECT_DELAY_SECONDS", "5")
            ),
            filter_online=os.getenv(
                "VALHEIM_LOG_FILTER_ONLINE", "Game server connected"
            ),
            filter_offline=os.getenv("VALHEIM_LOG_FILTER_OFFLINE", "Shutting down"),
            filter_join=os.getenv(
                "VALHEIM_LOG_FILTER_JOIN", "Got character ZDOID from"
            ),
            filter_leave=os.getenv("VALHEIM_LOG_FILTER_LEAVE", "Closing socket"),
            filter_raid=os.getenv("VALHEIM_LOG_FILTER_RAID", "Random event set:"),
            filter_death=os.getenv(
                "VALHEIM_LOG_FILTER_DEATH", "got status effect Dead"
            ),
            discord_webhook_debug=_clean_url(os.getenv("DISCORD_WEBHOOK_DEBUG")),
            discord_webhook_log=_clean_url(os.getenv("DISCORD_WEBHOOK_LOG")),
            discord_webhook_players=_clean_url(os.getenv("DISCORD_WEBHOOK_PLAYERS")),
            webhook_timeout_seconds=float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5")),
            webhook_retry_delay_seconds=float(
                os.getenv("WEBHOOK_RETRY_DELAY_SECONDS", "1")
            ),
            timezone_name=os.getenv("TZ", "UTC"),
            backups_enabled=_parse_bool(os.getenv("BACKUPS", "false")),
            backups_cron=os.getenv("BACKUPS_CRON"),
            backup_grace_minutes=int(os.getenv("BACKUP_GRACE_MINUTES", "25")),
            backup_suppress_before_minutes=int(
                os.getenv("BACKUP_SUPPRESS_BEFORE_MINUTES", "5")
            ),
            backup_suppress_after_minutes=int(
                os.getenv("BACKUP_SUPPRESS_AFTER_MINUTES", "25")
            ),
            backup_healthcheck_interval_seconds=int(
                os.getenv("BACKUP_HEALTHCHECK_INTERVAL_SECONDS", "30")
            ),
            healthcheck_udp_port=int(os.getenv("HEALTHCHECK_UDP_PORT", "2456")),
        )


def _clean_url(value: str | None) -> str | None:
    """Normalize environment URL-like values.

    Parameters
    ----------
    value : str | None
        Raw environment value.

    Returns
    -------
    str | None
        Stripped non-empty value or ``None``.
    """
    if value is None:
        return None

    stripped = value.strip()
    if stripped == "":
        return None
    return stripped


def _parse_bool(value: str) -> bool:
    """Parse a string boolean value.

    Parameters
    ----------
    value : str
        Raw environment boolean value.

    Returns
    -------
    bool
        Parsed boolean.
    """
    return value.strip().lower() in {"1", "true", "yes", "on"}
