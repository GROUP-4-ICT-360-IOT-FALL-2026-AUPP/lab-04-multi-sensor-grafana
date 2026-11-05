import network
from machine import Pin, ADC
import time
import json
from umqtt.simple import MQTTClient

# ---- Settings ----
SSID = "Robotic WIFI"
PASSWORD = "rbtWIFI@2025"

BROKER = "10.30.0.99"
PORT = 1883
TOPIC = b"gas/mq5"
CLIENT_ID = b"esp32-mq5-robotics-7f3a"
KEEPALIVE = 30

WARNING_LEVEL = 2100
DANGER_LEVEL = 2600


# ---- WiFi ----
def wifi_connect():
    wlan = network.WLAN(network.STA_IF)

    if wlan.active():
        try:
            wlan.disconnect()
        except OSError:
            pass
        wlan.active(False)
        time.sleep(1)

    wlan.active(True)
    time.sleep(1)

    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(SSID, PASSWORD)
        t0 = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > 20000:
                raise RuntimeError("Wi-Fi connect timeout")
            time.sleep(0.3)
    print("WiFi OK:", wlan.ifconfig())
    return wlan


# ---- Moving average ----
N = 5
readings = []

def moving_average(new_value):
    readings.append(new_value)
    if len(readings) > N:
        readings.pop(0)
    return sum(readings) / len(readings)


# ---- Risk level ----
def check_risk(value):
    if value >= DANGER_LEVEL:
        return "Danger"
    elif value >= WARNING_LEVEL:
        return "Warning"
    else:
        return "Safe"


# ---- MQTT ----
def make_client():
    return MQTTClient(client_id=CLIENT_ID, server=BROKER,
                      port=PORT, keepalive=KEEPALIVE)

def connect_mqtt(c):
    time.sleep(0.5)
    c.connect()
    print("MQTT connected")


def main():
    wlan = wifi_connect()

    mq5 = ADC(Pin(33))
    mq5.atten(ADC.ATTN_11DB)
    mq5.width(ADC.WIDTH_12BIT)

    client = make_client()
    connect_mqtt(client)

    while True:
        try:
            gas_value = mq5.read()
            avg_value = moving_average(gas_value)
            risk_level = check_risk(avg_value)

            voltage = (gas_value / 4095) * 3.3
            avg_voltage = (avg_value / 4095) * 3.3

            print("Raw ADC Value:", gas_value)
            print("Averaged Value: {:.1f}".format(avg_value))
            print("Voltage: {:.2f} V (avg: {:.2f} V)".format(voltage, avg_voltage))
            print("Risk:", risk_level)
            print("----------------------")

            payload = json.dumps({
                "raw": gas_value,
                "avg": round(avg_value, 1),
                "voltage": round(voltage, 2),
                "avg_voltage": round(avg_voltage, 2),
                "risk": risk_level
            })
            client.publish(TOPIC, payload)

        except OSError as e:
            print("Connection error:", e, "- reconnecting...")
            try:
                try:
                    client.disconnect()
                except Exception:
                    pass

                if not wlan.isconnected():
                    wlan = wifi_connect()

                client = make_client()
                connect_mqtt(client)
            except Exception as e2:
                print("Reconnect failed:", e2)
                time.sleep(3)

        time.sleep(1)


main()
