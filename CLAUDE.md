# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Run

```bash
pip install -r requirements.txt
# Required env: OWNTRACKS_PASSWORD and VIEWER_PASSWORD must be set or the
# corresponding endpoints reject every request.
OWNTRACKS_PASSWORD=... VIEWER_PASSWORD=... python wsgi.py     # dev, port 5000
gunicorn wsgi:application                                     # prod entry point
```

There are no tests, no lint config, and no build step.

## Architecture

Single Flask app (`app/__init__.py::create_app`) that does two things behind HTTP Basic auth:

1. **Ingest** — `POST /pub` accepts OwnTracks JSON pings (auth: `OWNTRACKS_USERNAME` / `OWNTRACKS_PASSWORD`). Only payloads with `_type == "location"` and both `lat`/`lon` are persisted; the entire payload is also stored verbatim in `locations.raw` so new fields can be backfilled later without changing the wire format. The endpoint always returns `[]` (OwnTracks expects a JSON array of friend locations).
2. **View** — `GET /` renders `templates/map.html` (Leaflet + OSM tiles, no build step, CDN-loaded). The page calls `GET /api/points?from=&to=` which returns a GeoJSON `FeatureCollection`. Both endpoints require the `viewer` realm (`VIEWER_USERNAME` / `VIEWER_PASSWORD`).

`from`/`to` accept either Unix epoch seconds or ISO 8601 (`Z` suffix is normalized to `+00:00`); naive datetimes are treated as UTC. See `_parse_ts` in `app/routes.py`.

### Storage

SQLite at `Config.DB_PATH` (env `LOC_DB_PATH`, default `<repo>/loc.sqlite3`). Note the committed `timeline.sqlite` is **not** the runtime path — set `LOC_DB_PATH` if you want to point at it. `app/db.py::init_db` runs `schema.sql` on every `create_app()`; the schema uses `IF NOT EXISTS`, so this is the migration story — edit `schema.sql` for additive changes, write a one-off script for anything destructive. WAL is enabled per-connection.

The `locations` table mirrors OwnTracks field names (`tst`, `tid`, `acc`, `alt`, `vel`, `cog`, `batt`, `bs`, `conn`, `trigger`) plus `raw` (full JSON) and `received_at` (server clock). Indexed on `tst` and `(tid, tst)`.

### Auth

`_check_basic_auth` uses `hmac.compare_digest` and returns False whenever the configured password is missing — there is intentionally no "no password = open" mode. Two separate realms (`owntracks`, `timeline`) so phone credentials and viewer credentials never overlap.
