"""Discord webhook sender with retry policy."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .routing import OutboundWebhook

LOGGER = logging.getLogger(__name__)

type SleepFn = Callable[[float], None]
type PostFn = Callable[[str, dict[str, str], float], int]


@dataclass(frozen=True)
class SendResult:
    """Outcome from sending one outbound webhook.

    Parameters
    ----------
    success : bool
        Whether delivery succeeded.
    attempts : int
        Number of HTTP attempts made.
    status_code : int | None
        Final HTTP status code when available.
    error : str | None
        Failure details when unsuccessful.
    """

    success: bool
    attempts: int
    status_code: int | None
    error: str | None = None


def send_with_retry(
    outbound: OutboundWebhook,
    *,
    timeout_seconds: float,
    retry_delay_seconds: float,
    post_fn: PostFn | None = None,
    sleep_fn: SleepFn = time.sleep,
) -> SendResult:
    """Send a webhook with one retry for transient failures.

    Parameters
    ----------
    outbound : OutboundWebhook
        Prepared outbound webhook request.
    timeout_seconds : float
        Timeout for each HTTP request.
    retry_delay_seconds : float
        Delay before retrying a transient failure.
    post_fn : PostFn, optional
        HTTP execution function used for testing and transport override.
    sleep_fn : SleepFn, optional
        Sleeper used between retry attempts.

    Returns
    -------
    SendResult
        Final delivery outcome.
    """
    if post_fn is None:
        post_fn = _post_json

    attempts = 0

    for _ in range(2):
        attempts += 1
        try:
            status_code = post_fn(outbound.url, outbound.payload, timeout_seconds)
        except (TimeoutError, URLError) as exc:
            is_last_attempt = attempts == 2
            if is_last_attempt:
                LOGGER.error(
                    "Webhook send failed for event_type=%s after retry: %s",
                    outbound.event_type,
                    exc,
                )
                return SendResult(
                    success=False, attempts=attempts, status_code=None, error=str(exc)
                )

            sleep_fn(retry_delay_seconds)
            continue

        if 200 <= status_code < 300:
            return SendResult(success=True, attempts=attempts, status_code=status_code)

        if 500 <= status_code < 600:
            if attempts == 2:
                LOGGER.error(
                    "Webhook send failed for event_type=%s with HTTP %s after retry",
                    outbound.event_type,
                    status_code,
                )
                return SendResult(
                    success=False,
                    attempts=attempts,
                    status_code=status_code,
                    error=f"http_{status_code}",
                )

            sleep_fn(retry_delay_seconds)
            continue

        LOGGER.error(
            "Webhook send failed for event_type=%s with non-retriable HTTP %s",
            outbound.event_type,
            status_code,
        )
        return SendResult(
            success=False,
            attempts=attempts,
            status_code=status_code,
            error=f"http_{status_code}",
        )

    return SendResult(
        success=False, attempts=attempts, status_code=None, error="unknown_failure"
    )


def _post_json(url: str, payload: dict[str, str], timeout_seconds: float) -> int:
    """Send a JSON payload with urllib and return status code.

    Parameters
    ----------
    url : str
        HTTP endpoint.
    payload : dict[str, str]
        JSON request body.
    timeout_seconds : float
        Request timeout.

    Returns
    -------
    int
        HTTP response code.
    """
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        url=url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "valheim-log-webhook/1.0",
            "Accept": "*/*",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status)
    except HTTPError as exc:
        return int(exc.code)
