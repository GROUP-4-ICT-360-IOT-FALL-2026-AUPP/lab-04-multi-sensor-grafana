import random
import env

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

URL = "http://localhost:8086"
ORG = "aupp"
BUCKET = "random-numbers"
TOKEN = env.TOKEN
WRITE_AMOUNT = 100

RANDOM_RANGE = (0, 100)

if __name__ == "__main__":
    with InfluxDBClient(url=URL, token=TOKEN, org=ORG) as client:
        with client.write_api(write_options=SYNCHRONOUS) as write_api:
            for _ in range(WRITE_AMOUNT):
                number = random.randint(*RANDOM_RANGE)

                point = (
                    Point("random_numbers")
                    .field("value", float(number))
                )

                write_api.write(
                    bucket=BUCKET,
                    record=point,
                )

                print(f"Wrote: {number}")
