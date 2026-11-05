import paho.mqtt.subscribe as subscribe
import json

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "lab4/environment"
MQTT_CLIENT_ID = "esp32-lab4-main-7f3a"



def main():
    while True:
        msg = subscribe.simple(MQTT_TOPIC, hostname=MQTT_BROKER, port=MQTT_PORT)
        print(f"Received topic: {msg.topic}")
        #print(f"Received payload: {msg.payload}")
        #print(f"Payload type: {type(msg.payload)}")
        print(json.loads(msg.payload))

if __name__ == "__main__":
    main()
