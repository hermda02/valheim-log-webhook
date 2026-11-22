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

## D-4 — Persist Steam ID to player-name mappings for player-leave notifications

- **Decision:** The sidecar maintains an internal Steam ID to player-name mapping learned from events that include both identifiers, persists that mapping to disk, and uses it to enrich player-leave messages.
- **Why:** Player-leave log lines may only include Steam ID, while player-facing notifications should show character names when known.
- **Rejected:** Keeping the mapping in memory only (loses names on process restart) and sending Steam ID-only leave messages (worse player readability).

## D-5 — Make the player map path configurable with a sensible default

- **Decision:** The persisted player map file path is configurable via `VALHEIM_PLAYER_MAP_PATH`, defaulting to `/tmp/valheim-player-map.json`.
- **Why:** Operators can keep the default for simple setups or point to a mounted persistent path for restart-safe behavior across container recreation.
- **Rejected:** Hardcoding one path with no override (less portable across deployments).
