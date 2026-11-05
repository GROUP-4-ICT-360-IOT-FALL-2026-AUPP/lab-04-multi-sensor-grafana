import paho.mqtt.subscribe as subscribe

MQTT_BROKER = "10.30.0.99"
MQTT_PORT = 1883
MQTT_TOPIC = b"lab4/environment"
MQTT_CLIENT_ID = b"esp32-lab4-main-7f3a"



def main():
    msg = subscribe.simple(MQTT_TOPIC, hostname=MQTT_BROKER, port=MQTT_PORT)
    print(f"Received topic: {msg.topic}")
    print(f"Received payload: {msg.payload.decode('utf-8')}")

if __name__ == "__main__":
    main()
