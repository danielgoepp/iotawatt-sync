# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python scripts that move electrical monitoring data from IoTaWatt units into a VictoriaMetrics time series database. Only the sync daemon is actively used; the transform script was a one-time migration.

## Architecture

**Core Components:**
- `vm_iotawatt_sync.py` - Long-running sync daemon (the only script in the Docker image). Every 5 minutes it pulls new data from the IoTaWatt units and imports it into VictoriaMetrics.
- `vm_iotawatt_transform.py` - One-time migration, already run. It does **not** talk to IoTaWatt: it reads the older `Power_<measurement>` series (from the InfluxDB era) out of VictoriaMetrics via `/api/v1/query_range` and re-imports them as `power{...}` with the same labels the sync script uses. Hardcoded end date `2025-01-31`.
- The measurement list and tagging rules are duplicated in both scripts. Change the sync script; the transform script is not maintained.

**Sync data flow (`vm_iotawatt_sync.py`):**
1. For each measurement, find the last stored sample: `max(tlast_over_time(power{location="X"}[30d]))`
2. Query the IoTaWatt (`http://{host}.goepp.net/query`) starting one 1m group after that sample, `group=1m`, paged with `limit=5000` (the response's `limit` field gives the next `begin`)
3. Build labels with `build_labels()` and import to VictoriaMetrics via `/api/v1/import`

**System Configuration:**
- Two IoTaWatt units: `iwatt5` (trunks and some circuits, data from 2021-09-18) and `iwatt6` (circuits, data from 2023-02-05)
- VictoriaMetrics endpoint: `https://vms-prod-lt.goepp.net`
- All data stored at 1-minute resolution, minute-aligned timestamps
- Environment overrides for the sync script: `VICTORIAMETRICS_URL`, `IOTAWATT_DOMAIN`, `SYNC_INTERVAL` (seconds)

## Development Commands

**Run sync daemon:**
```bash
python vm_iotawatt_sync.py
```

**Run the one-time migration (not normally needed):**
```bash
python vm_iotawatt_transform.py
```

**Build Docker image:**
```bash
docker build -t iotawatt-sync .
```

**Build on the dev server and push to GHCR (ghcr.io/danielgoepp/iotawatt-sync):**
```bash
./build-and-push.sh
```

Images are published to GitHub Container Registry (not Docker Hub), tagged `:latest` and `:<git-short-sha>`. CI (`.github/workflows/docker-image.yml`) builds on every push/PR and pushes to GHCR on pushes to `main` using `GITHUB_TOKEN`. Running `build-and-push.sh` manually requires a one-time `docker login ghcr.io -u danielgoepp` with a PAT that has `write:packages`. It refuses to push from a dirty working tree unless `ALLOW_DIRTY=1`; `NO_PUSH=1` builds only.

**Install dependencies:**
```bash
pip install -r requirements.txt
```

## Key Implementation Details

**Labels (`build_labels()`):**
- Every series: `__name__="power"`, `location=<measurement>`, `device=<host>`, `source="iotawatt"`
- `Mains_*`, `SolarA_*`, `SolarB_*`, `Garage_*` → `type="Trunk"`, `pair=<prefix>`; `Solar*` also gets `solar="Both"`
- `Minisplit*`, `OfficeHeat`, `BathroomHeat`, `Furnace` → `hvac="True"`; `Minisplit*` also gets `minisplit="True"`
- Everything else → `type="Circuit"`

**Error handling (sync):**
- All HTTP calls have timeouts (`REQUEST_TIMEOUT`).
- If VictoriaMetrics can't be queried for the last sample, that measurement is skipped for this run. The fallback start date is only used when VM really has no data in the last 30 days (this re-pulls full history, so expect a long catch-up).
- If an import fails, paging stops for that measurement so later pages can't move the last-sample time past a gap; the next run retries from the last stored sample.
- Failures for one measurement don't stop the others.

**Gotchas:**
- The next IoTaWatt query must start a whole group (60s) after the last sample. A non-aligned `begin` makes IoTaWatt return an extra off-grid sample at that exact time.
- Re-importing the same timestamp into VictoriaMetrics creates duplicate samples unless VM runs with `-dedup.minScrapeInterval`.
