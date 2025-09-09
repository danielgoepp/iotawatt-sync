# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based IoTaWatt data synchronization system that transfers electrical monitoring data from IoTaWatt units to VictoriaMetrics time series database. The project consists of two main scripts for handling historical data migration and ongoing synchronization.

## Architecture

**Core Components:**
- `vm_iotawatt_sync.py` - Continuous sync daemon that runs every 5 minutes to pull new data
- `vm_iotawatt_transform.py` - One-time historical data loader for initial migration
- Both scripts use the same measurement configuration and tagging logic

**Data Flow:**
1. Query IoTaWatt units via HTTP API (`http://{host}.goepp.net/query`)
2. Transform raw power measurements into VictoriaMetrics JSON format
3. Apply device-specific tags (trunk/circuit classification, HVAC grouping, solar pairing)
4. Write to VictoriaMetrics via `/api/v1/import` endpoint

**System Configuration:**
- Two IoTaWatt units: `iwatt5` (main/trunk data from 2021-09-18) and `iwatt6` (circuit data from 2023-02-05)
- VictoriaMetrics endpoint: `https://vms-prod-lt.goepp.net`
- All data downsampled to 1-minute resolution
- Sync looks back 30 days maximum for last data point

## Development Commands

**Run sync daemon:**
```bash
python vm_iotawatt_sync.py
```

**Run historical data loader:**
```bash
python vm_iotawatt_transform.py
```

**Build Docker image:**
```bash
docker build -t iotawatt-sync .
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

## Key Implementation Details

**Measurement Configuration:**
- Measurements are defined in `measurements_all` dictionary with device-specific lists
- Each measurement gets tagged with location, device, source, and type-specific metadata

**Tagging Logic:**
- `Mains_*`, `SolarA_*`, `SolarB_*`, `Garage_*` → trunk circuits with pair grouping
- `Minisplit*`, `*Heat`, `Furnace` → HVAC classification
- All others → circuit classification

**Error Handling:**
- Sync script continues on individual measurement failures
- Historical loader processes data in 7-day chunks to handle large datasets
- Both scripts include comprehensive logging and exception handling

**API Integration:**
- IoTaWatt uses query parameters for time ranges, grouping, and limits
- VictoriaMetrics expects specific JSON format with metric, values, and timestamps arrays
- Sync script handles pagination via IoTaWatt's `limit` response field