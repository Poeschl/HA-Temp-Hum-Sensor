#!/usr/bin/python
import time

import Adafruit_DHT
import paho.mqtt.client as mqtt

sensor = Adafruit_DHT.DHT22
pin = 4
value_average_count = 5

startup_readings = 3
temp_storage = []
hum_storage = []

mqtt_client_name = 'my-pi'
mqtt_host = 'broker.host'
mqtt_port = 1883
mqtt_user = 'user'
mqtt_pass = 'pass'


def get_sensor_values():
    return Adafruit_DHT.read_retry(sensor, pin)


def compute_temp(mqtt_client, temp):
    global temp_storage
    if temp is not None and -20 < temp < 50:
        if len(temp_storage) == 0 or abs(temp_storage[len(temp_storage) - 1] - temp) < 10:
            temp_storage.append(temp)
    else:
        print('Ignoring temp: ' + str(temp))

    if len(temp_storage) == value_average_count:
        average = calc_average(temp_storage)
        mqtt_client.publish(mqtt_temp_sensor_topic, average, retain=True)
        print("Sending: " + str(average) + '°C')
        temp_storage.clear()


def compute_huminity(mqtt_client, hum):
    global hum_storage
    if hum is not None and 0 < hum < 100:
        if len(hum_storage) == 0 or abs(hum_storage[len(hum_storage) - 1] - hum) < 10:
            hum_storage.append(hum)
    else:
        print('Ignoring hum: ' + str(hum))

    if len(hum_storage) == value_average_count:
        average = calc_average(hum_storage)
        mqtt_client.publish(mqtt_hum_sensor_topic, average, retain=True)
        print("Sending: " + str(average) + '%')
        hum_storage.clear()


def calc_average(array):
    sum = 0
    for elem in array:
        sum = sum + elem
    return round(sum / len(array), 1)


def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        print('Connected to broker(' + mqtt_host + ').')
        send_ha_autodiscovery(client)
        print('Sent autodiscovery for HA')
    else:
        print('Not connect to broker(' + mqtt_host + '). Errorcode: ' + str(rc))


def send_ha_autodiscovery(mqtt_client):
    ha_discover_topic_template = 'homeassistant/sensor/%s_%s/config'
    ha_discover_content_temp = '{"name":"%s Temperature",' \
                               '"device_class":"temperature",' \
                               '"unit_of_measurement":"°C",' \
                               '"state_topic": "%s"}' % (mqtt_client_name, mqtt_temp_sensor_topic)
    ha_discover_content_hum = '{"name":"%s Humidity",' \
                              '"device_class":"humidity",' \
                              '"unit_of_measurement":"%%",' \
                              '"state_topic": "%s"}' % (mqtt_client_name, mqtt_hum_sensor_topic)

    temp_topic = ha_discover_topic_template % (mqtt_client_name, 'temperature')
    hum_topic = ha_discover_topic_template % (mqtt_client_name, 'humidity')

    mqtt_client.publish(temp_topic, ha_discover_content_temp, retain=True)
    mqtt_client.publish(hum_topic, ha_discover_content_hum, retain=True)


mqtt_prefix = mqtt_client_name + '/sensor/'
mqtt_temp_sensor_topic = mqtt_prefix + 'temperature/state'
mqtt_hum_sensor_topic = mqtt_prefix + 'humidity/state'


def main():
    global startup_readings

    mqtt_client = mqtt.Client(mqtt_client_name)
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.username_pw_set(mqtt_user, mqtt_pass)
    mqtt_client.connect(mqtt_host, mqtt_port)

    while True:
        mqtt_client.loop()
        humidity, temperature = get_sensor_values()

        if startup_readings == 0:
            compute_temp(mqtt_client, temperature)
            compute_huminity(mqtt_client, humidity)

            mqtt_client.loop()
            time.sleep(5)
        else:
            # Skip the first readings to get the sensor running
            startup_readings = startup_readings - 1
            print('Take values in ' + str(startup_readings) + ' readings.')


if __name__ == '__main__':
    main()
