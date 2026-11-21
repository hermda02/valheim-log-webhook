"""Backup suppression and post-backup health-check tests."""

from __future__ import annotations

from datetime import UTC, datetime

from valheim_log_webhook.config import RuntimeConfig
from valheim_log_webhook.maintenance import BackupCoordinator


def _config() -> RuntimeConfig:
    return RuntimeConfig(
        container_name="valheim-server",
        reconnect_delay_seconds=0.01,
        filter_online="Game server connected",
        filter_offline="Shutting down",
        filter_join="Got character ZDOID from",
        filter_leave="Closing socket",
        filter_raid="Random event set:",
        filter_death="got status effect Dead",
        backups_enabled=True,
        backups_cron="5 4 * * *",
        backup_grace_minutes=25,
        backup_suppress_before_minutes=5,
        backup_suppress_after_minutes=25,
        timezone_name="Europe/Oslo",
    )


def test_suppression_is_active_inside_backup_window() -> None:
    now = datetime(2026, 1, 1, 3, 10, tzinfo=UTC)
    coordinator = BackupCoordinator(_config(), now_fn=lambda: now)

    assert coordinator.suppression_active() is True


def test_suppression_is_inactive_outside_backup_window() -> None:
    now = datetime(2026, 1, 1, 5, 0, tzinfo=UTC)
    coordinator = BackupCoordinator(_config(), now_fn=lambda: now)

    assert coordinator.suppression_active() is False


def test_scheduled_healthcheck_emits_offline_once_per_day() -> None:
    now_holder = {"now": datetime(2026, 1, 1, 3, 30, tzinfo=UTC)}
    unhealthy_calls = {"count": 0}

    def on_unhealthy() -> None:
        unhealthy_calls["count"] += 1

    coordinator = BackupCoordinator(
        _config(),
        now_fn=lambda: now_holder["now"],
        healthcheck_fn=lambda _config: False,
    )

    coordinator.run_scheduled_healthcheck(on_unhealthy)
    coordinator.run_scheduled_healthcheck(on_unhealthy)

    assert unhealthy_calls["count"] == 1


def test_scheduled_healthcheck_skips_alert_when_healthy() -> None:
    now = datetime(2026, 1, 1, 3, 30, tzinfo=UTC)
    unhealthy_calls = {"count": 0}

    coordinator = BackupCoordinator(
        _config(),
        now_fn=lambda: now,
        healthcheck_fn=lambda _config: True,
    )

    coordinator.run_scheduled_healthcheck(
        lambda: unhealthy_calls.__setitem__("count", 1)
    )

    assert unhealthy_calls["count"] == 0
