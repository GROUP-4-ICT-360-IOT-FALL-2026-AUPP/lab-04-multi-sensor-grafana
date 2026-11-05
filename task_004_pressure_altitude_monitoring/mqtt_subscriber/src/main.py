import random
import env
import json
from datetime import datetime, UTC

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import paho.mqtt.subscribe as subscribe

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "lab4/environment"
MQTT_CLIENT_ID = "esp32-lab4-main-7f3a"

URL = "http://localhost:8086"
ORG = "aupp"
BUCKET = "lab-04-task-04"
TOKEN = env.TOKEN

if __name__ == "__main__":

    with InfluxDBClient(url=URL, token=TOKEN, org=ORG) as client:
        with client.write_api(write_options=SYNCHRONOUS) as write_api:
            while True:
                msg = subscribe.simple(MQTT_TOPIC, hostname=MQTT_BROKER, port=MQTT_PORT)
                data_point = data_point = {
                    "measurement": "lab-04-task-04-measurement",
                    "tags": {
                        "server": "linux laptop"
                    },
                    "fields": json.loads(msg.payload),
                    "time": datetime.now(UTC)
                }
                write_api.write(
                    bucket=BUCKET,
                    record=data_point,
                )
                print(data_point)
