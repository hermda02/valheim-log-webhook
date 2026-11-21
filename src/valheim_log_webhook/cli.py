"""CLI entrypoint for sidecar runtime behavior."""

from __future__ import annotations

import logging
import os
import threading
import time

from .app import process_lines, send_scheduled_offline_alert
from .config import RuntimeConfig
from .events import ParseMiss
from .logstream import follow_container_logs
from .maintenance import BackupCoordinator

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Run the Phase 1 sidecar loop.

    Returns
    -------
    int
        POSIX process exit code.
    """
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level_name, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = RuntimeConfig.from_env()
    backup_coordinator = BackupCoordinator(config)
    _start_backup_monitor(config, backup_coordinator)

    line_stream = follow_container_logs(config)

    process_lines(
        line_stream,
        config,
        on_parse_miss=_log_parse_miss,
        backup_coordinator=backup_coordinator,
    )

    return 0


def _log_parse_miss(miss: ParseMiss) -> None:
    """Log parse misses at debug level.

    Parameters
    ----------
    miss : ParseMiss
        Parse miss details.
    """
    LOGGER.debug("parse_miss reason=%s line=%s", miss.reason, miss.line)


def _start_backup_monitor(
    config: RuntimeConfig, backup_coordinator: BackupCoordinator
) -> None:
    """Start a daemon thread for scheduled post-backup health checks.

    Parameters
    ----------
    config : RuntimeConfig
        Runtime configuration.
    backup_coordinator : BackupCoordinator
        Backup suppression and health-check coordinator.
    """

    def worker() -> None:
        while True:
            backup_coordinator.run_scheduled_healthcheck(
                lambda: send_scheduled_offline_alert(config)
            )
            time.sleep(max(1, config.backup_healthcheck_interval_seconds))

    thread = threading.Thread(
        target=worker, name="backup-healthcheck-monitor", daemon=True
    )
    thread.start()


if __name__ == "__main__":
    raise SystemExit(main())
