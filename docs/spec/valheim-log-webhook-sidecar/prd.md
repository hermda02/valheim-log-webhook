# Valheim Log Webhook Sidecar

Build a simple containerized tool that follows `valheim-server` logs and sends Discord webhooks for selected game and lifecycle events. This gives players and operators timely status updates without relying on inline shell hooks inside the game server container.

## Status

- Stage: Ready
- Slug: valheim-log-webhook-sidecar

## Problem

Current webhook behavior is embedded in environment hook commands, which is hard to maintain, hard to test, and tightly coupled to server startup scripts. We need a separate small tool that watches logs and emits stable notifications.

## Scope

**In**

- Run as a separate containerized follower that reads logs from a running `valheim-server` container.
- Detect and notify on server online, server offline, player join, player leave, raid start, and player death events.
- Send Discord webhook notifications to configured channels for debug/log/player-facing messages.

**Out**

- Backup-success or backup-failure webhook behavior.
- Generic non-Discord webhook providers.
- Replacing or changing Valheim server runtime behavior.

**Do not change**

- Existing `valheim-server` container image and startup command.
- Existing webhook endpoint ownership and Discord-side configuration.

## Constraints

- The tool must run containerized and external to the `valheim-server` container.
- Configuration must be via environment variables so it can be deployed with Docker compose-style workflows.
- Discord webhook URLs are sensitive and must not be written to emitted log lines except where already masked by runtime configuration.

## Approach

The sidecar continuously follows `valheim-server` logs, matches known log patterns for the selected events, transforms each match into a Discord message with a stable event prefix, and posts it to the mapped webhook channel with minimal retry behavior.

## Requirements

### FR-1 Log follow source

The tool must follow logs from a running `valheim-server` container using Docker log streaming.

- When the configured target container is running and emits new lines, then the tool consumes those lines continuously.
- When the target container is missing, stopped, or inaccessible, then the tool records an operator-visible error and retries connection until access is restored.

### FR-2 Event detection coverage

The tool must detect exactly the v1 event set: server online, server offline, player join, player leave, raid start, and player death.

- When an input line matches one of the configured v1 event patterns, then the corresponding event type is emitted once with event-specific extracted data when present.
- When an input line does not match a v1 event pattern or lacks required parseable fields, then no webhook is sent for that line and a debug-level parse miss is recorded.

### FR-3 Discord routing and payloads

The tool must send event notifications to Discord incoming webhooks using fixed channel mapping from environment variables.

- When an event is emitted, then the tool sends an HTTP POST payload to the mapped Discord webhook URL for that event category.
- When the mapped webhook URL is unset or invalid for an event category, then the send is skipped, an operator-visible error is recorded, and processing continues for subsequent events.

### FR-4 Delivery retry behavior

The tool must use best-effort webhook delivery with one retry for transient failures.

- When a webhook request fails due to timeout, network error, or HTTP `5xx`, then the tool retries that same payload exactly once before marking it failed.
- When a webhook request fails with HTTP `4xx`, then the tool does not retry and records the failure with status code context.

## Open Questions

- None
