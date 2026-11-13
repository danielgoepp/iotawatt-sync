"""Continuously sync IoTaWatt power readings into VictoriaMetrics.

Every SYNC_INTERVAL seconds, for each measurement: find the last sample stored
in VictoriaMetrics, fetch newer 1-minute data from the IoTaWatt unit, and
import it into VictoriaMetrics.
"""

import json
import logging
import os
import time

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

VICTORIAMETRICS_URL = os.environ.get(
    "VICTORIAMETRICS_URL", "https://vms-prod-lt.goepp.net"
)
IOTAWATT_DOMAIN = os.environ.get("IOTAWATT_DOMAIN", "goepp.net")
SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL", "300"))
LOOKBACK = "30d"  # how far back to search VictoriaMetrics for the last sample
GROUP_SECONDS = 60  # IoTaWatt query resolution ("1m")
PAGE_LIMIT = 5000  # rows per IoTaWatt query
REQUEST_TIMEOUT = (5, 60)  # (connect, read) seconds

# Where to start when a measurement has no data in VictoriaMetrics.
HOST_START_DATES = {
    "iwatt5": "2021-09-18",
    "iwatt6": "2023-02-05",
}

measurements_all = {
    "iwatt5": [
        "Mains_1",
        "Mains_2",
        "SolarA_1",
        "SolarA_2",
        "SolarB_1",
        "SolarB_2",
        "Garage_1",
        "Garage_2",
        "MinisplitGreatAndBlue",
        "MinisplitBedAndStudio",
        "EastWall",
        "BathroomHeat",
        "OfficeHeat",
        "Dryer",
    ],
    "iwatt6": [
        "Office",
        "Furnace",
        "OGMaker",
        "LaundryFoyerMaker",
        "GreatroomSouthTV",
        "Datacenter",
        "BlueAndBreeze",
        "StudioA",
        "Freezers",
        "Bedroom",
        "StudioASouth",
        "Dishwasher",
        "Washer",
        "Fridge",
    ],
}

TRUNK_PAIRS = ("Mains", "SolarA", "SolarB", "Garage")
HVAC_PREFIXES = ("Minisplit", "OfficeHeat", "BathroomHeat", "Furnace")


def build_labels(host, measurement):
    """Return the VictoriaMetrics label set for a measurement."""
    labels = {
        "__name__": "power",
        "location": measurement,
        "source": "iotawatt",
        "device": host,
        "type": "Circuit",
    }

    for pair in TRUNK_PAIRS:
        if measurement.startswith(pair):
            labels["pair"] = pair
            labels["type"] = "Trunk"
    if measurement.startswith("Solar"):
        labels["solar"] = "Both"
    if measurement.startswith(HVAC_PREFIXES):
        labels["hvac"] = "True"
    if measurement.startswith("Minisplit"):
        labels["minisplit"] = "True"

    return labels


def write_to_vm(host, measurement, rows):
    """Import IoTaWatt [unix_seconds, watts] rows. Returns True on success."""
    data_point = {
        "metric": build_labels(host, measurement),
        "values": [float(value) for _, value in rows],
        "timestamps": [int(ts * 1000) for ts, _ in rows],
    }

    try:
        response = requests.post(
            f"{VICTORIAMETRICS_URL}/api/v1/import",
            data=json.dumps(data_point),
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Write to VictoriaMetrics failed for {measurement}: {e}")
        return False
    return True


def vm_get_last_time(measurement):
    """Return the unix time of the newest stored sample, or None if there is none.

    Raises requests.exceptions.RequestException if VictoriaMetrics can't be
    queried, so callers can tell "no data" apart from "VM unavailable".
    """
    params = {
        "query": f'max(tlast_over_time(power{{location="{measurement}"}}[{LOOKBACK}]))'
    }
    response = requests.get(
        f"{VICTORIAMETRICS_URL}/api/v1/query", params=params, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    result = response.json()["data"]["result"]
    if not result:
        return None
    return int(float(result[0]["value"][1]))


def vm_get_iotawatt_data(host, measurement, begin):
    """Fetch data from IoTaWatt starting at `begin` and write it to VM, page by page."""
    query_params = {
        "select": f"[time.utc.unix,{measurement}]",
        "begin": begin,
        "end": "s",
        "group": "1m",
        "missing": "skip",
        "limit": str(PAGE_LIMIT),
        "header": "yes",
    }

    while True:
        try:
            response = requests.get(
                f"http://{host}.{IOTAWATT_DOMAIN}/query",
                params=query_params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"Failed to fetch {measurement} from {host}: {e}")
            return

        rows = body.get("data", [])
        if not rows:
            logger.debug(f"No new data for {measurement}")
            return

        # Stop paging on a failed write; otherwise later pages would advance
        # the last-sample time in VM and leave a permanent gap.
        if not write_to_vm(host, measurement, rows):
            return

        if "limit" not in body:
            return
        query_params["begin"] = body["limit"]


def sync_once():
    for host, measurements in measurements_all.items():
        for measurement in measurements:
            try:
                last_time = vm_get_last_time(measurement)
            except (requests.exceptions.RequestException, ValueError, KeyError) as e:
                # Don't fall back to the start date here: that would re-pull the
                # full history from the IoTaWatt whenever VM is briefly unavailable.
                logger.error(f"Skipping {measurement}: can't read last time from VM: {e}")
                continue

            if last_time is not None:
                # Start at the next 1m group so samples stay minute-aligned.
                begin = last_time + GROUP_SECONDS
            else:
                begin = HOST_START_DATES[host]
                logger.warning(
                    f"No data in the last {LOOKBACK} for {measurement} - starting from {begin}"
                )
            vm_get_iotawatt_data(host, measurement, begin)


if __name__ == "__main__":
    while True:
        logger.info("Running sync")
        sync_once()
        logger.info(f"Done - sleeping {SYNC_INTERVAL}s")
        time.sleep(SYNC_INTERVAL)
