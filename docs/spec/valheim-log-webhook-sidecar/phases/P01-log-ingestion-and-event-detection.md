# Phase 1: Log Ingestion and Event Detection

Deliver a running sidecar flow that can attach to `valheim-server` logs and produce normalized internal events for the v1 event set.

## Exit Criteria

- [ ] The sidecar can continuously consume new log lines from a running `valheim-server` container and recover from missing or stopped container states by retrying.
- [ ] The sidecar emits one normalized internal event per matching line for online, offline, join, leave, raid, and death, and records parse misses for non-matching or incomplete lines.

## P01-001 Runtime configuration and Docker log stream attachment

Define runtime configuration for selecting the target container and start a continuous Docker log stream reader that can reconnect after access failures. This establishes the required external sidecar log-follow behavior.

Covers: FR-1

- [ ] With a running target container, starting the sidecar results in continuous intake of newly emitted log lines.
- [ ] With a missing, stopped, or inaccessible target container, the sidecar reports an operator-visible connection error and retries until log access is restored.

## P01-002 Event parser for the v1 pattern set

Implement parsing rules that match Valheim log lines and emit normalized event objects for server online, server offline, player join, player leave, raid start, and player death, including extracted fields when available.

Covers: FR-2
Depends on: P01-001

- [ ] For one representative line per v1 event type, parsing emits exactly one event object with the correct event type and extracted values where present.
- [ ] For unrelated lines and lines missing required parseable fields, parsing emits no event object and records a debug-level parse miss signal.
