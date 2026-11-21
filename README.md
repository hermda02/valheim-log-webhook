# Valheim Log Webhook Sidecar

Containerized sidecar that follows `valheim-server` logs and sends Discord webhook notifications.

It is backup-aware: offline notifications are suppressed around backup time, and a down alert is only sent after the configured post-backup grace period if health checks still fail.

## Build

```bash
docker build -t valheim-log-webhook:local .
```

## Docker Compose Snippet

Add this service next to your existing `valheim-server` service:

```yaml
services:
  valheim-log-webhook:
    image: valheim-log-webhook:local
    container_name: valheim-log-webhook
    restart: unless-stopped
    environment:
      TZ: Europe/Oslo
      BACKUPS: "true"
      BACKUPS_CRON: "5 4 * * *"
      BACKUP_GRACE_MINUTES: "25"
      BACKUP_SUPPRESS_BEFORE_MINUTES: "5"
      BACKUP_SUPPRESS_AFTER_MINUTES: "25"
      BACKUP_HEALTHCHECK_INTERVAL_SECONDS: "30"
      HEALTHCHECK_UDP_PORT: "2456"
      VALHEIM_CONTAINER_NAME: valheim-server
      LOG_LEVEL: INFO
      LOG_RECONNECT_DELAY_SECONDS: "5"
      WEBHOOK_TIMEOUT_SECONDS: "5"
      WEBHOOK_RETRY_DELAY_SECONDS: "1"
      DISCORD_WEBHOOK_DEBUG: ${DISCORD_WEBHOOK_DEBUG}
      DISCORD_WEBHOOK_LOG: ${DISCORD_WEBHOOK_LOG}
      DISCORD_WEBHOOK_PLAYERS: ${DISCORD_WEBHOOK_PLAYERS}
      # Optional filter overrides:
      # VALHEIM_LOG_FILTER_ONLINE: "Game server connected"
      # VALHEIM_LOG_FILTER_OFFLINE: "Shutting down"
      # VALHEIM_LOG_FILTER_JOIN: "Got character ZDOID from"
      # VALHEIM_LOG_FILTER_LEAVE: "Closing socket"
      # VALHEIM_LOG_FILTER_RAID: "Random event set:"
      # VALHEIM_LOG_FILTER_DEATH: "got status effect Dead"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

## Run

```bash
docker compose up -d valheim-log-webhook
docker compose logs -f valheim-log-webhook
```

Note: this sidecar uses Docker log streaming from the host daemon, so it needs read access to `/var/run/docker.sock` and a Docker CLI in the sidecar image.

## Backup-Aware Down Alerts

- Offline log events are suppressed inside the backup window (`BACKUP_SUPPRESS_BEFORE_MINUTES` to `BACKUP_SUPPRESS_AFTER_MINUTES` around `BACKUPS_CRON`).
- After `BACKUP_GRACE_MINUTES`, a scheduled health check runs once per day for that backup cycle.
- If health checks still fail, one offline webhook is sent.
- Health check order is: UDP port listener check (`ss`), fallback listener check (`netstat`), then process check (`pgrep valheim_server.x86_64`) inside the `valheim-server` container.
