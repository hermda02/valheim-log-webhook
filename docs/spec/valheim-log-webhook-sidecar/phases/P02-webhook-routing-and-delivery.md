# Phase 2: Webhook Routing and Delivery

Deliver Discord notification delivery from normalized events with fixed env-based channel mapping and retry behavior.

## Exit Criteria

- [ ] Each v1 event type is routed to the expected Discord webhook category from environment configuration.
- [ ] Delivery retries exactly once for timeout, network, and HTTP 5xx failures, and does not retry HTTP 4xx failures.

## P02-001 Discord routing map and payload formatter

Add Discord-specific routing that maps normalized event categories to configured webhook URLs from environment variables and formats stable event-prefixed message payloads.

Covers: FR-3
Depends on: P01-002

- [ ] For each v1 event type, routing selects the configured debug, log, or players webhook target according to the fixed mapping.
- [ ] If a required webhook URL is unset or invalid, the send is skipped, an operator-visible error is recorded, and subsequent events continue processing.

## P02-002 Webhook sender with one-retry transient failure policy

Implement the outbound Discord webhook sender with best-effort delivery, including one retry for transient failures and terminal handling for non-retriable failures.

Covers: FR-4
Depends on: P02-001

- [ ] On timeout, network error, or HTTP 5xx response, the sender performs exactly one retry of the same payload before marking failure.
- [ ] On HTTP 4xx response, the sender performs no retry and records failure details including HTTP status code.

## P02-003 End-to-end event-to-webhook pipeline integration

Wire log intake, event parsing, routing, and sending into one continuous processing loop so detected v1 events become Discord notifications while parse misses and delivery failures remain observable to operators.

Covers: FR-1, FR-2, FR-3, FR-4
Depends on: P02-002

- [ ] In an integration run that feeds representative v1 log lines, each line produces one outbound webhook call to the expected configured channel.
- [ ] In the same run, non-matching or incomplete lines produce no outbound webhook call and emit a debug-level parse miss signal.
