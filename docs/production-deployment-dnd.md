# Production Deployment Guide (dnd.iamjeeves.dev)

This document describes the production deployment foundation for the DnD Initiative Tracker.

## Deployment Overview

The application is intended to run as a headless backend service on `dnd.iamjeeves.dev`.

### Filesystem Layout

Target user: `init-tracker`
Home directory: `/home/init-tracker`

| Path | Description |
| --- | --- |
| `/home/init-tracker/app` | Application source code (git checkout) - **Contains canonical content (Monsters, Spells, etc.)** |
| `/home/init-tracker/data` | Runtime mutable data (sessions, settings, profile uploads) |
| `/home/init-tracker/logs` | Application logs |
| `/home/init-tracker/releases` | Deployment releases/artifacts |
| `/home/init-tracker/venv` | Python virtual environment |

## Content and Data Separation

The current deployment foundation separates mutable runtime data from canonical source content:

- **Canonical Content:** Directories such as `Monsters/`, `Spells/`, `Items/`, `players/`, and `assets/` currently remain within the application source tree (`INIT_TRACKER_APP_DIR`). This simplifies deployment of the standard content library.
- **Runtime Data:** Mutable data such as `sessions/`, `settings/lan_url.json`, and generated monster source data are redirected to `INIT_TRACKER_DATA_DIR`.
- **Logs:** All application logs are redirected to `INIT_TRACKER_LOG_DIR`.

Future passes may implement a layered overlay system if it becomes necessary to support custom content outside the app tree in production.

## Environment Configuration

The application uses environment variables for configuration. In production, these should be managed via an environment file, for example `/etc/init-tracker/init-tracker.env`.

### Supported Environment Variables

| Variable | Description | Default (Dev) |
| --- | --- | --- |
| `INIT_TRACKER_MODE` | Runtime mode (`production` or `development`) | `development` |
| `INIT_TRACKER_HOME` | Base home directory for structured paths | N/A |
| `INIT_TRACKER_APP_DIR` | Application source directory | Current directory |
| `INIT_TRACKER_DATA_DIR` | Runtime data directory | `~/Documents/Dnd-Init-Yamls` |
| `INIT_TRACKER_LOG_DIR` | Log directory | `$DATA_DIR/logs` |
| `INIT_TRACKER_RELEASES_DIR` | Releases directory | `$DATA_DIR/releases` |
| `INIT_TRACKER_HOST` | LAN server bind host | `0.0.0.0` |
| `INIT_TRACKER_PORT` | LAN server bind port | `8787` |
| `INIT_TRACKER_PUBLIC_BASE_URL` | Public URL for the tracker | N/A |

Note: Legacy `INITTRACKER_*` (no underscore) variables are still supported for backward compatibility but the underscored versions are preferred.

### Example Production Environment File

```bash
# /etc/init-tracker/init-tracker.env

INIT_TRACKER_MODE=production
INIT_TRACKER_HOME=/home/init-tracker
INIT_TRACKER_APP_DIR=/home/init-tracker/app
INIT_TRACKER_DATA_DIR=/home/init-tracker/data
INIT_TRACKER_LOG_DIR=/home/init-tracker/logs
INIT_TRACKER_RELEASES_DIR=/home/init-tracker/releases

INIT_TRACKER_HOST=127.0.0.1
INIT_TRACKER_PORT=8787
INIT_TRACKER_PUBLIC_BASE_URL=https://dnd.iamjeeves.dev/

# LAN Admin
INIT_TRACKER_ADMIN_PASSWORD=your_secure_password
```

## Launching in Production

Use `serve_headless.py` for production server mode.

```bash
/home/init-tracker/venv/bin/python3 /home/init-tracker/app/serve_headless.py
```

Directories specified in `INIT_TRACKER_DATA_DIR`, `INIT_TRACKER_LOG_DIR`, and `INIT_TRACKER_RELEASES_DIR` will be created automatically on startup if `INIT_TRACKER_MODE=production`.

## Systemd Integration (Deferred)

Systemd service unit creation is deferred to a future pass.

## Reverse Proxy (Caddy)

Refer to the main `README.md` for Caddy + HTTPS configuration details. The production deployment expects Caddy to handle TLS and proxy to the application's bind host/port.
