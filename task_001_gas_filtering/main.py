import network
from machine import Pin, ADC
import time
import json
from umqtt.simple import MQTTClient
import socket

# ---- Settings ----
SSID = "Robotic WIFI"
PASSWORD = "rbtWIFI@2025"

BROKER = "10.30.0.99"
PORT = 1883
TOPIC = b"gas/mq5"
CLIENT_ID = b"esp32-mq5-robotics-7f3a"
KEEPALIVE = 30

# ---- WiFi ----
def wifi_connect():
    wlan = network.WLAN(network.STA_IF)

    # Only reset the radio if it's already in some state
    if wlan.active():
        try:
            wlan.disconnect()
        except OSError:
            pass
        wlan.active(False)
        time.sleep(1)          # give the driver time to shut down

    wlan.active(True)
    time.sleep(1)              # give it time to come up

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

def test_broker():
    print("Testing broker reachability...")
    try:
        addr = socket.getaddrinfo(BROKER, PORT)[0][-1]
        print("Resolved:", addr)
    except Exception as e:
        print("DNS FAILED:", e)
        return False
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect(addr)
        print("TCP connect OK")
        return True
    except Exception as e:
        print("TCP CONNECT FAILED:", e)
        return False
    finally:
        s.close()


# ---- Moving average ----
N = 5
readings = []

def moving_average(new_value):
    readings.append(new_value)
    if len(readings) > N:
        readings.pop(0)
    return sum(readings) / len(readings)


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
    test_broker() 

    mq5 = ADC(Pin(33))
    mq5.atten(ADC.ATTN_11DB)
    mq5.width(ADC.WIDTH_12BIT)

    client = make_client()
    connect_mqtt(client)

    while True:
        try:
            gas_value = mq5.read()
            avg_value = moving_average(gas_value)

            voltage = (gas_value / 4095) * 3.3
            avg_voltage = (avg_value / 4095) * 3.3

            print("Raw ADC Value:", gas_value)
            print("Averaged Value: {:.1f}".format(avg_value))
            print("Voltage: {:.2f} V (avg: {:.2f} V)".format(voltage, avg_voltage))
            print("----------------------")
            
            payload = json.dumps({
        "raw": gas_value,
        "avg": round(avg_value, 1),
        "voltage": round(voltage, 2),
        "avg_voltage": round(avg_voltage, 2)
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
