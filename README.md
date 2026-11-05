# Wiring

Wiring diagram (from the assignment):

![](./assets/wiring_diagram.png)

# General Idea

We read the sensor data, processes it and then send the data from the ESP32 to an MQTT broker.

MQTT is a protocol that works over TCP, and we publish it to the MQTT broker, and then we can subscribe to the MQTT broker to receive the data.

We can then take that data and save it to a database, and then view it in Grafana.

# Task 1

Task 1 essentially just reads from the gas sensor and then send it to the MQTT broker.

The code for task 1 is located [here](./task_001_gas_filtering/main.py)

The flowchart for task 1 is as follows:

![](./flowcharts/output/task_001.svg)

Example of it running:

![](./assets/task_001.jpg)

# Task 2

Task 2 just updates task 1 so that we also send warning levels.

The flowchart for task 2 is as follows:

![](./flowcharts/output/task_002.svg)

The code for task 2 is located [here](./task_001_gas_filtering/main.py)

Example of it running:

![task 2 gas sensor showing warning levels](./assets/task_002_warning.jpg)

![task 2 gas sensor showing safe levels](./assets/task_002_safe.jpg)

# Task 3

Task 3 reads the body temperature and then send it to the MQTT broker.

The flowchart for task 3 is as follows:

![](./flowcharts/output/task_003.svg)

The code for task 3 is located [here](./task_003_fever_detection_logic/main.py)

# Task 4

Task 4 is divided into 2 parts:

- the MQTT publisher (ESP32)
- the MQTT subscriber (Seperate computer with a database server)

## MQTT publisher

The code for the MQTT publisher is located here.
