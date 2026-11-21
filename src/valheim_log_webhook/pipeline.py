"""Pipeline helpers for stream parsing."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

from .config import RuntimeConfig
from .events import NormalizedEvent, ParseMiss
from .parser import parse_line


def parse_stream(
    lines: Iterable[str],
    config: RuntimeConfig,
    on_parse_miss: Callable[[ParseMiss], None],
) -> Iterator[NormalizedEvent]:
    """Convert a raw line stream into normalized events.

    Parameters
    ----------
    lines : Iterable[str]
        Raw log lines to parse.
    config : RuntimeConfig
        Runtime parser configuration.
    on_parse_miss : Callable[[ParseMiss], None]
        Callback invoked for every non-emitting parse result.

    Yields
    ------
    NormalizedEvent
        Parsed event values.
    """
    for line in lines:
        result = parse_line(line=line, config=config)
        if isinstance(result, ParseMiss):
            on_parse_miss(result)
            continue

        yield result
