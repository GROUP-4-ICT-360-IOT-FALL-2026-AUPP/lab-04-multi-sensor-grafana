import network
from machine import Pin, I2C
import time
import json
from umqtt.simple import MQTTClient

# ================= Settings =================
SSID = "Robotic WIFI"
PASSWORD = "rbtWIFI@2025"

BROKER = "10.30.0.99"
PORT = 1883
TOPIC = b"lab4/fever"
CLIENT_ID = b"esp32-lab4-task3-7f3a"
KEEPALIVE = 30

FEVER_THRESHOLD = 32.5      # deg C
MLX_ADDR = 0x5A


# ================= WiFi =================
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


# ================= Fever detection =================
def mlx_read_temp(i2c, reg):
    """reg 0x06 = ambient, 0x07 = object (body). Returns deg C."""
    data = i2c.readfrom_mem(MLX_ADDR, reg, 3)      # low, high, PEC
    raw = data[0] | (data[1] << 8)
    return raw * 0.02 - 273.15

def fever_detect(body_temp):
    if body_temp >= FEVER_THRESHOLD:
        return 1
    return 0


# ================= MQTT =================
def make_client():
    return MQTTClient(client_id=CLIENT_ID, server=BROKER,
                      port=PORT, keepalive=KEEPALIVE)

def connect_mqtt(c):
    time.sleep(0.5)
    c.connect()
    print("MQTT connected")


# ================= Main =================
def main():
    wlan = wifi_connect()

    # I2C bus: SDA = D21, SCL = D22
    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)
    print("I2C devices found:", [hex(a) for a in i2c.scan()])   # expect 0x5a

    client = make_client()
    connect_mqtt(client)

    while True:
        try:
            try:
                body_temp = mlx_read_temp(i2c, 0x07)
            except OSError:
                body_temp = -1
                print("MLX90614 read failed")

            fever_flag = fever_detect(body_temp)

            print("Body temp: {:.2f} C".format(body_temp))
            print("fever_flag:", fever_flag)
            print("----------------------")

            payload = json.dumps({
                "body_temp": round(body_temp, 2),
                "fever_flag": fever_flag
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
