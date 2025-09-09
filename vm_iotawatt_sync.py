from datetime import datetime
import requests
import json
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

victoriametrics_server = "https://vms-prod-lt.goepp.net"
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


def write_to_vm(host, measurement, data):
    metric = {}
    values = []
    timestamps = []

    metric["__name__"] = "power"
    metric["location"] = measurement
    metric["source"] = "iotawatt"
    metric["device"] = host

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

    for entry in data:
        values.append(float(entry[1]))
        timestamps.append(int(entry[0] * 1000))

    data_point = {
        "metric": metric,
        "values": values,
        "timestamps": timestamps,
    }

    try:
        write_response = requests.post(
            f"{victoriametrics_server}/api/v1/import",
            data=json.dumps(data_point),
            headers={"Content-Type": "application/json"},
        )
        write_response.raise_for_status()

    except requests.exceptions.RequestException as e:
        logger.error(f"Error during API request: {e}")


## Get the last time data was fetched
def vm_get_last_time(measurment):

    try:
        params = {
            "query": f'tlast_over_time(power{{location="{measurment}"}})',
            "step": "30d",
        }

        response = requests.get(f"{victoriametrics_server}/api/v1/query", params=params)

        if response.status_code != 200:
            raise Exception(f"Error fetching data: {response.text}")

        if not response.json()["data"]["result"]:
            raise Exception(f"No data found for {measurment}")

        start_time = int(response.json()["data"]["result"][0]["value"][1])
        return start_time

    except requests.exceptions.RequestException as e:
        logger.error(f"Error during API request: {e}")
    except Exception as e:
        logger.error(f"Error processing data: {e}")


## Get the data from IoTaWatt
def vm_get_iotawatt_data(host, measurement, start_time):

    response = {}
    query_params = {
        "select": f"[time.utc.unix,{measurement}]",
        "begin": start_time,
        "end": "s",
        "group": "1m",
        "missing": "skip",
        "limit": "5000",
        "header": "yes",
    }

    while True:
        if response != {}:
            if "limit" in response.json().keys():
                query_params["begin"] = response.json()["limit"]
            else:
                break

        if isinstance(query_params["begin"], str):
            show_time = query_params["begin"]
        else:
            show_time = datetime.fromtimestamp(query_params["begin"])

        # logger.info(f"Transferring {measurement} from {show_time} on {host}")

        try:
            response = requests.get(
                f"http://{host}.goepp.net/query", params=query_params
            )

            if response.status_code != 200:
                raise Exception(f"Error fetching data: {response.text}")

            if response.json()["data"] == []:
                raise Exception("No new data available")

            write_to_vm(host, measurement, response.json()["data"])

        except Exception as e:
            logger.error(f"Failed to fetch data from IoTaWatt: {str(e)}")
            break

        # time.sleep(1)


if __name__ == "__main__":

    while True:
        logger.info(f"Running sync {datetime.now().isoformat('T', 'seconds')}")
        for host, measurements in measurements_all.items():
            for measurement in measurements:
                start_time = vm_get_last_time(measurement)
                if start_time is not None:
                    vm_get_iotawatt_data(host, measurement, start_time + 5)
                else:
                    if host == "iwatt6":
                        start_time = "2023-02-05"
                    elif host == "iwatt5":
                        start_time = "2021-09-18"
                    logger.warning(
                        f"No last time found for {measurement} - using {start_time}"
                    )
                    vm_get_iotawatt_data(host, measurement, start_time)
        logger.info(f"Done at {datetime.now().isoformat('T', 'seconds')} - Sleep 5m")
        time.sleep(300)
