#!/usr/bin/env python3

import requests
from datetime import datetime, timedelta, timezone
import logging
import json

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def get_time_chunks(start_time, end_time, chunk_size_days):
    start_time = datetime.fromisoformat(start_time).timestamp()
    end_time = datetime.fromisoformat(end_time).timestamp()

    chunk_size = timedelta(days=chunk_size_days).total_seconds() - 1
    current_start = start_time

    while current_start < end_time:
        current_end = min(current_start + chunk_size, end_time)
        yield current_start, current_end
        current_start = current_end + 1


if __name__ == "__main__":

    vm_url = f"https://vms-prod-lt.goepp.net/"
    end_time = "2025-01-31T23:59:59+00:00"
    source_step = "1m"
    target_step = "1m"
    chunk_size_days = 7

    for host, measurements in measurements_all.items():

        if host == "iwatt5":
            start_time = "2021-09-18T00:00:00+00:00"
        elif host == "iwatt6":
            start_time = "2023-02-05T00:00:00+00:00"

        for measurement in measurements:

            for chunk_start, chunk_end in get_time_chunks(
                start_time, end_time, chunk_size_days
            ):

                try:

                    params = {
                        "query": f"Power_{measurement}",
                        "start": chunk_start,
                        "end": chunk_end,
                        "step": source_step,
                    }

                    response = requests.get(
                        f"{vm_url}api/v1/query_range", params=params
                    )
                    response.raise_for_status()

                    if response.status_code != 200:
                        raise Exception(f"Error fetching data: {response.text}")

                    if (
                        "data" not in response.json()
                        or len(response.json()["data"]["result"]) == 0
                    ):
                        raise ValueError("No data found in response")

                    result = response.json()["data"]["result"][0]

                    metric = result["metric"].copy()
                    metric["__name__"] = "power"
                    metric["location"] = measurement
                    metric["source"] = "iotawatt"

                    if measurement.startswith("Mains"):
                        metric["pair"] = "Mains"
                        metric["type"] = "Trunk"
                    if measurement.startswith("SolarA"):
                        metric["pair"] = "SolarA"
                        metric["type"] = "Trunk"
                    if measurement.startswith("SolarB"):
                        metric["pair"] = "SolarB"
                        metric["type"] = "Trunk"
                    if measurement.startswith("Solar"):
                        metric["solar"] = "Both"
                    if measurement.startswith("Garage"):
                        metric["pair"] = "Garage"
                        metric["type"] = "Trunk"
                    if measurement.startswith("Minisplit"):
                        metric["hvac"] = "True"
                        metric["minisplit"] = "True"
                    if measurement.startswith("OfficeHeat"):
                        metric["hvac"] = "True"
                    if measurement.startswith("BathroomHeat"):
                        metric["hvac"] = "True"
                    if measurement.startswith("Furnace"):
                        metric["hvac"] = "True"

                    if "type" not in metric:
                        metric["type"] = "Circuit"

                    values = []
                    timestamps = []

                    for timestamp, value in result["values"]:
                        values.append(float(value))
                        timestamps.append(int(timestamp * 1000))

                    data_point = {
                        "metric": metric,
                        "values": values,
                        "timestamps": timestamps,
                    }

                    logger.info(
                        f"Write: {host} - {measurement} {datetime.fromtimestamp(chunk_start,tz=timezone.utc)} to {datetime.fromtimestamp(chunk_end,tz=timezone.utc)}: {len(data_point['values'])}"
                    )
                    write_response = requests.post(
                        f"{vm_url}/api/v1/import",
                        data=json.dumps(data_point),
                        headers={"Content-Type": "application/json"},
                    )
                    write_response.raise_for_status()

                except requests.exceptions.RequestException as e:
                    logger.error(f"Error during API request: {e}")
                except Exception as e:
                    logger.error(f"Error processing data: {e}")
