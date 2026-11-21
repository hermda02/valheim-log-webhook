"""Docker log stream follower with reconnect behavior."""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable, Iterator

from .config import RuntimeConfig

LOGGER = logging.getLogger(__name__)

type SleepFn = Callable[[float], None]
type StopFn = Callable[[], bool]
type PopenFn = Callable[..., subprocess.Popen[str]]


def build_logs_command(container_name: str) -> list[str]:
    """Build the Docker command used to follow container logs.

    Parameters
    ----------
    container_name : str
        Name of the target container.

    Returns
    -------
    list[str]
        Command argv for subprocess execution.
    """
    return ["docker", "logs", "--follow", "--tail", "0", container_name]


def follow_container_logs(
    config: RuntimeConfig,
    *,
    popen_fn: PopenFn = subprocess.Popen,
    sleep_fn: SleepFn = time.sleep,
    stop_fn: StopFn = lambda: False,
) -> Iterator[str]:
    """Yield log lines from a Docker container with reconnect retries.

    Parameters
    ----------
    config : RuntimeConfig
        Runtime settings including container name and reconnect delay.
    popen_fn : PopenFn, optional
        Process factory used to start Docker logs.
    sleep_fn : SleepFn, optional
        Sleeper callable used between retries.
    stop_fn : StopFn, optional
        Callable that requests graceful loop termination.

    Yields
    ------
    str
        One newline-stripped log line.
    """
    command = build_logs_command(config.container_name)

    while not stop_fn():
        try:
            process = popen_fn(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            LOGGER.error(
                "Cannot attach to container logs for '%s': %s",
                config.container_name,
                exc,
            )
            sleep_fn(config.reconnect_delay_seconds)
            continue

        if process.stdout is None:
            LOGGER.error("Docker logs stream opened without stdout; retrying")
            sleep_fn(config.reconnect_delay_seconds)
            continue

        for line in process.stdout:
            if stop_fn():
                return
            yield line.rstrip("\n")

        return_code = process.wait()
        stderr_output = ""
        if process.stderr is not None:
            stderr_output = process.stderr.read().strip()

        if return_code == 0:
            LOGGER.error(
                "Log stream ended for '%s'; reconnecting",
                config.container_name,
            )
        else:
            LOGGER.error(
                "Cannot read container logs for '%s' (exit=%s): %s",
                config.container_name,
                return_code,
                stderr_output,
            )

        sleep_fn(config.reconnect_delay_seconds)
