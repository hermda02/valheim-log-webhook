"""Backup-aware notification suppression and health checks."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import RuntimeConfig

LOGGER = logging.getLogger(__name__)

type HealthCheckFn = Callable[[RuntimeConfig], bool]
type NowFn = Callable[[], datetime]


class BackupCoordinator:
    """Coordinate backup-window suppression and delayed down-alert checks.

    Parameters
    ----------
    config : RuntimeConfig
        Runtime configuration.
    now_fn : NowFn, optional
        Clock provider for deterministic tests.
    healthcheck_fn : HealthCheckFn, optional
        Container responsiveness check.
    """

    def __init__(
        self,
        config: RuntimeConfig,
        *,
        now_fn: NowFn | None = None,
        healthcheck_fn: HealthCheckFn | None = None,
    ) -> None:
        self._config = config
        self._now_fn = _utc_now if now_fn is None else now_fn
        self._healthcheck_fn = (
            is_container_responsive if healthcheck_fn is None else healthcheck_fn
        )
        self._schedule = _parse_daily_schedule(config.backups_cron)
        self._timezone = _resolve_timezone(config.timezone_name)
        self._last_healthcheck_key: date | None = None

    def suppression_active(self) -> bool:
        """Return whether server-down messages should be suppressed now."""
        if not self._config.backups_enabled or self._schedule is None:
            return False

        local_now = self._now_fn().astimezone(self._timezone)
        backup_start = local_now.replace(
            hour=self._schedule[0],
            minute=self._schedule[1],
            second=0,
            microsecond=0,
        )

        window_start = backup_start - timedelta(
            minutes=self._config.backup_suppress_before_minutes
        )
        window_end = backup_start + timedelta(
            minutes=self._config.backup_suppress_after_minutes
        )
        return window_start <= local_now <= window_end

    def run_scheduled_healthcheck(self, on_unhealthy: Callable[[], None]) -> None:
        """Run one post-backup health check per backup day when due.

        Parameters
        ----------
        on_unhealthy : Callable[[], None]
            Callback invoked when server is still unhealthy after grace period.
        """
        if not self._config.backups_enabled or self._schedule is None:
            return

        local_now = self._now_fn().astimezone(self._timezone)
        backup_start = local_now.replace(
            hour=self._schedule[0],
            minute=self._schedule[1],
            second=0,
            microsecond=0,
        )
        due_at = backup_start + timedelta(minutes=self._config.backup_grace_minutes)

        if local_now < due_at:
            return

        if self._last_healthcheck_key == backup_start.date():
            return

        healthy = self._healthcheck_fn(self._config)
        self._last_healthcheck_key = backup_start.date()

        if healthy:
            LOGGER.info("Post-backup health check passed")
            return

        LOGGER.error("Post-backup health check failed after grace period")
        on_unhealthy()


def is_container_responsive(config: RuntimeConfig) -> bool:
    """Check whether Valheim container appears responsive.

    Parameters
    ----------
    config : RuntimeConfig
        Runtime configuration containing container name and health port.

    Returns
    -------
    bool
        ``True`` when the server appears healthy.
    """
    running_cmd = [
        "docker",
        "inspect",
        "-f",
        "{{.State.Running}}",
        config.container_name,
    ]
    running = subprocess.run(running_cmd, capture_output=True, text=True, check=False)
    if running.returncode != 0:
        return False

    if running.stdout.strip() != "true":
        return False

    port = str(config.healthcheck_udp_port)
    checks = [
        [
            "docker",
            "exec",
            config.container_name,
            "sh",
            "-lc",
            f"ss -H -lun 2>/dev/null | awk '{{print $5}}' | grep -Eq '(^|:){port}$'",
        ],
        [
            "docker",
            "exec",
            config.container_name,
            "sh",
            "-lc",
            f"netstat -lun 2>/dev/null | awk '{{print $4}}' | grep -Eq '(^|:){port}$'",
        ],
        [
            "docker",
            "exec",
            config.container_name,
            "sh",
            "-lc",
            "pgrep -f 'valheim_server\\.x86_64' >/dev/null",
        ],
    ]

    for command in checks:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return True

    return False


def _parse_daily_schedule(cron_expression: str | None) -> tuple[int, int] | None:
    """Parse hour/minute from a simple five-field cron expression."""
    if cron_expression is None:
        return None

    fields = cron_expression.split()
    if len(fields) != 5:
        LOGGER.error("Unsupported BACKUPS_CRON value: %s", cron_expression)
        return None

    minute_field, hour_field = fields[0], fields[1]
    if not minute_field.isdigit() or not hour_field.isdigit():
        LOGGER.error("Unsupported BACKUPS_CRON value: %s", cron_expression)
        return None

    hour = int(hour_field)
    minute = int(minute_field)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        LOGGER.error("Unsupported BACKUPS_CRON value: %s", cron_expression)
        return None

    return hour, minute


def _resolve_timezone(timezone_name: str) -> ZoneInfo:
    """Resolve configured timezone with a safe UTC fallback."""
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        LOGGER.error("Unknown timezone '%s'; falling back to UTC", timezone_name)
        return ZoneInfo("UTC")


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(tz=UTC)
