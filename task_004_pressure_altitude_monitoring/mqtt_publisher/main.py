import network
from machine import Pin, I2C, ADC
import time
import json
import struct
from umqtt.simple import MQTTClient

# ================= Settings =================
SSID = "Robotic WIFI"
PASSWORD = "rbtWIFI@2025"

BROKER = "test.mosquitto.org"
PORT = 1883
TOPIC = b"lab4/environment"
CLIENT_ID = b"esp32-lab4-main-7f3a"
KEEPALIVE = 30

SEA_LEVEL_HPA = 1013.25
BMP_ADDR = 0x76             # change to 0x77 if the I2C scan shows 0x77
RTC_ADDR = 0x68
MLX_ADDR = 0x5A

GAS_PIN = 33                # MQ-5 A0 -> D33 (matches the lab wiring)
GAS_WINDOW = 5              # moving average of the last 5 samples

WARNING_LEVEL = 2100        # lab thresholds
DANGER_LEVEL = 2600
FEVER_THRESHOLD = 32.5      # deg C


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


# ================= BMP280 driver (pressure) =================
class BMP280:
    def __init__(self, i2c, addr=BMP_ADDR):
        self.i2c = i2c
        self.addr = addr
        cal = i2c.readfrom_mem(addr, 0x88, 24)
        (self.T1, self.T2, self.T3,
         self.P1, self.P2, self.P3, self.P4, self.P5,
         self.P6, self.P7, self.P8, self.P9) = struct.unpack("<HhhHhhhhhhhh", cal)
        i2c.writeto_mem(addr, 0xF4, bytes([0x2F]))
        i2c.writeto_mem(addr, 0xF5, bytes([0x10]))
        time.sleep_ms(100)
        self.t_fine = 0

    def read_pressure(self):
        """Returns pressure in hPa."""
        d = self.i2c.readfrom_mem(self.addr, 0xF7, 6)
        adc_p = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
        adc_t = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4)

        v1 = (((adc_t >> 3) - (self.T1 << 1)) * self.T2) >> 11
        v2 = (((((adc_t >> 4) - self.T1) * ((adc_t >> 4) - self.T1)) >> 12) * self.T3) >> 14
        self.t_fine = v1 + v2

        v1 = self.t_fine - 128000
        v2 = v1 * v1 * self.P6
        v2 = v2 + ((v1 * self.P5) << 17)
        v2 = v2 + (self.P4 << 35)
        v1 = ((v1 * v1 * self.P3) >> 8) + ((v1 * self.P2) << 12)
        v1 = (((1 << 47) + v1) * self.P1) >> 33
        if v1 == 0:
            return 0.0
        p = 1048576 - adc_p
        p = (((p << 31) - v2) * 3125) // v1
        v1 = (self.P9 * (p >> 13) * (p >> 13)) >> 25
        v2 = (self.P8 * p) >> 19
        p = ((p + v1 + v2) >> 8) + (self.P7 << 4)
        return p / 25600


def calc_altitude(pressure_hpa):
    if pressure_hpa <= 0:
        return 0.0
    return 44330 * (1 - (pressure_hpa / SEA_LEVEL_HPA) ** 0.1903)


# ================= DS3231 RTC (timestamp) =================
def bcd2dec(b):
    return (b >> 4) * 10 + (b & 0x0F)

def dec2bcd(d):
    return ((d // 10) << 4) | (d % 10)

def rtc_set(i2c, year, month, day, hour, minute, second):
    """Run ONCE to set the RTC, then comment the call out again."""
    i2c.writeto_mem(RTC_ADDR, 0x00, bytes([
        dec2bcd(second), dec2bcd(minute), dec2bcd(hour),
        1, dec2bcd(day), dec2bcd(month), dec2bcd(year - 2000)
    ]))

def rtc_timestamp(i2c):
    d = i2c.readfrom_mem(RTC_ADDR, 0x00, 7)
    sec = bcd2dec(d[0] & 0x7F)
    minute = bcd2dec(d[1])
    hour = bcd2dec(d[2] & 0x3F)
    day = bcd2dec(d[4])
    month = bcd2dec(d[5] & 0x1F)
    year = 2000 + bcd2dec(d[6])
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        year, month, day, hour, minute, sec)


# ================= Gas sensor (moving average) =================
class GasSensor:
    def __init__(self, pin_no, window=GAS_WINDOW):
        self.adc = ADC(Pin(pin_no))
        self.adc.atten(ADC.ATTN_11DB)       # full 0-3.3 V range
        self.adc.width(ADC.WIDTH_12BIT)     # 0-4095
        self.window = window
        self.history = []

    def read(self):
        """Returns (raw, average of the last N raw readings)."""
        raw = self.adc.read()
        self.history.append(raw)
        if len(self.history) > self.window:
            self.history.pop(0)
        return raw, sum(self.history) / len(self.history)


def check_risk(value):
    if value >= DANGER_LEVEL:
        return "DANGER", 2
    elif value >= WARNING_LEVEL:
        return "WARNING", 1
    return "SAFE", 0


# ================= Body temperature (MLX90614) =================
class BodyTemp:
    def __init__(self, i2c):
        self.i2c = i2c

    def read(self):
        """Object (body) temperature in deg C."""
        data = self.i2c.readfrom_mem(MLX_ADDR, 0x07, 3)   # low, high, PEC
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
    print("I2C devices found:", [hex(a) for a in i2c.scan()])   # expect 0x5a, 0x68, 0x76

    bmp = BMP280(i2c)
    gas = GasSensor(GAS_PIN)
    temp = BodyTemp(i2c)

    # Uncomment ONCE to set the DS3231 time, run, then comment it out again:
    # rtc_set(i2c, 2026, 11, 5, 14, 30, 0)

    client = make_client()
    connect_mqtt(client)

    while True:
        try:
            # --- Gas: raw, moving average, risk ---
            gas_raw, gas_avg = gas.read()
            risk_level, risk_code = check_risk(gas_avg)

            # --- Body temperature + fever flag ---
            try:
                body_temp = temp.read()
                fever_flag = fever_detect(body_temp)
            except OSError:
                body_temp, fever_flag = None, None
                print("MLX90614 read failed")

            # --- Pressure and altitude ---
            try:
                pressure = bmp.read_pressure()
                altitude = calc_altitude(pressure)
            except OSError:
                pressure, altitude = 0, 0
                print("BMP280 read failed")

            # --- Timestamp ---
            try:
                timestamp = rtc_timestamp(i2c)
            except OSError:
                timestamp = "RTC_ERROR"
                print("DS3231 read failed")

            print("Time:", timestamp)
            print("Gas raw: {}  avg: {:.1f}  risk: {}".format(gas_raw, gas_avg, risk_level))
            print("Body temp:", body_temp, " fever_flag:", fever_flag)
            print("Pressure: {:.2f} hPa  Altitude: {:.1f} m".format(pressure, altitude))
            print("----------------------")

            data = {
                "timestamp": timestamp,
                "gas_raw": gas_raw,
                "gas_avg": round(gas_avg, 1),
                "risk_level": risk_level,
                "risk_code": risk_code,
                "pressure": round(pressure, 2),
                "altitude": round(altitude, 1),
            }
            if body_temp is not None:          # skip the fields if the sensor fails
                data["body_temp"] = round(body_temp, 2)
                data["fever_flag"] = fever_flag

            client.publish(TOPIC, json.dumps(data))


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

