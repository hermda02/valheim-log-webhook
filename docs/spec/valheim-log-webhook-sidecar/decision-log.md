# Decision Log — valheim-log-webhook-sidecar

## D-1 — Follow Docker container logs directly

- **Decision:** The tool will read logs via `docker logs -f` semantics from the running `valheim-server` container.
- **Why:** This keeps the server container unchanged and avoids introducing shared file-path assumptions for log access.
- **Rejected:** Reading from a mounted log file path (more filesystem coupling) and supporting both sources in v1 (larger scope).

## D-2 — Keep v1 event scope small with core player and lifecycle events

- **Decision:** v1 covers server online, server offline, player join, player leave, raid start, and player death.
- **Why:** This delivers the most useful operator/player signals immediately while keeping parsing and testing scope small.
- **Rejected:** Backup events and full parity with all existing hook logic, which increases scope and implementation risk for the first release.

## D-3 — Discord-only webhooks with fixed env mapping

- **Decision:** v1 sends Discord incoming webhooks only, with fixed routing by environment variables for debug, log, and players channels, and one retry on transient failure.
- **Why:** This matches current operational usage and minimizes configuration complexity in the initial version.
- **Rejected:** Generic multi-provider webhook support and per-event dynamic routing in v1 due to added configuration and validation complexity.
