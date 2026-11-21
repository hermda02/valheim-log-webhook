"""Logstream follower retry behavior tests."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

from valheim_log_webhook.config import RuntimeConfig
from valheim_log_webhook.logstream import follow_container_logs


@dataclass
class FakeProcess:
    """Minimal process test double for docker log follower."""

    lines: list[str]
    return_code: int
    stderr_text: str

    def __post_init__(self) -> None:
        self.stdout = iter(self.lines)
        self.stderr = StringIO(self.stderr_text)

    def wait(self) -> int:
        return self.return_code


def _config() -> RuntimeConfig:
    return RuntimeConfig(
        container_name="valheim-server",
        reconnect_delay_seconds=0.001,
        filter_online="Game server connected",
        filter_offline="Shutting down",
        filter_join="Got character ZDOID from",
        filter_leave="Closing socket",
        filter_raid="Random event set:",
        filter_death="got status effect Dead",
    )


def test_follow_container_logs_retries_after_connection_error() -> None:
    attempts = {"count": 0}
    stop = {"value": False}
    sleeps: list[float] = []

    def popen_fn(*_args: object, **_kwargs: object) -> FakeProcess:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OSError("docker unavailable")
        return FakeProcess(
            lines=["line-1\n", "line-2\n"], return_code=1, stderr_text="missing"
        )

    def sleep_fn(seconds: float) -> None:
        sleeps.append(seconds)
        if attempts["count"] >= 2:
            stop["value"] = True

    def stop_fn() -> bool:
        return stop["value"]

    lines = list(
        follow_container_logs(
            _config(),
            popen_fn=popen_fn,
            sleep_fn=sleep_fn,
            stop_fn=stop_fn,
        )
    )

    assert lines == ["line-1", "line-2"]
    assert attempts["count"] == 2
    assert sleeps == [
        _config().reconnect_delay_seconds,
        _config().reconnect_delay_seconds,
    ]


def test_follow_container_logs_retries_after_nonzero_exit() -> None:
    attempts = {"count": 0}
    sleeps: list[float] = []

    def popen_fn(*_args: object, **_kwargs: object) -> FakeProcess:
        attempts["count"] += 1
        return FakeProcess(lines=[], return_code=1, stderr_text="No such container")

    def stop_fn() -> bool:
        return attempts["count"] >= 1

    list(
        follow_container_logs(
            _config(),
            popen_fn=popen_fn,
            sleep_fn=sleeps.append,
            stop_fn=stop_fn,
        )
    )

    assert attempts["count"] == 1
    assert sleeps == [_config().reconnect_delay_seconds]


def test_follow_container_logs_builds_expected_command() -> None:
    captured: list[list[str]] = []

    def popen_fn(*args: object, **_kwargs: object) -> FakeProcess:
        command = args[0]
        assert isinstance(command, list)
        captured.append(command)
        return FakeProcess(lines=[], return_code=0, stderr_text="")

    list(
        follow_container_logs(
            _config(),
            popen_fn=popen_fn,
            sleep_fn=lambda _seconds: None,
            stop_fn=lambda: len(captured) >= 1,
        )
    )

    assert captured == [["docker", "logs", "--follow", "--tail", "0", "valheim-server"]]
