#!/usr/bin/python
import time
import datetime

import Adafruit_DHT
import paho.mqtt.client as mqtt

sensor = Adafruit_DHT.DHT22
pin = 4
startup_readings = 3
send_interval = datetime.timedelta(minutes=2)

mqtt_client_name = 'my-pi'
mqtt_host = 'broker.host'
mqtt_port = 1883
mqtt_user = 'user'
mqtt_pass = 'pass'

def get_sensor_values():
    return Adafruit_DHT.read_retry(sensor, pin)


def compute_temp(temp):
    if temp is not None and -20 < temp < 40:
        if len(temp_storage) == 0 or abs(temp_storage[len(temp_storage) - 1] - temp) < 10:
            temp_storage.append(temp)
    else:
        print('Ignoring temp: ' + str(temp))


def compute_huminity(hum):
    if hum is not None and 0 < hum < 100:
        if len(hum_storage) == 0 or abs(hum_storage[len(hum_storage) - 1] - hum) < 10:
            hum_storage.append(hum)
    else:
        print('Ignoring hum: ' + str(hum))


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
                               '"state_topic": "%s", \
                               "availability_topic":"%s"}' % (mqtt_client_name, mqtt_temp_sensor_topic, mqtt_availability_topic)
    ha_discover_content_hum = '{"name":"%s Humidity",' \
                              '"device_class":"humidity",' \
                              '"unit_of_measurement":"%%",' \
                              '"state_topic": "%s", \
                               "availability_topic":"%s"}' % (mqtt_client_name, mqtt_hum_sensor_topic, mqtt_availability_topic)

    temp_topic = ha_discover_topic_template % (mqtt_client_name, 'temperature')
    hum_topic = ha_discover_topic_template % (mqtt_client_name, 'humidity')

    mqtt_client.publish(mqtt_availability_topic, 'online', retain=True)
    mqtt_client.publish(temp_topic, ha_discover_content_temp, retain=True)
    mqtt_client.publish(hum_topic, ha_discover_content_hum, retain=True)


def send_measurements(mqtt_client):
    global temp_storage
    global hum_storage
    average_temp = calc_average(temp_storage)
    average_hum = calc_average(hum_storage)

    mqtt_client.publish(mqtt_temp_sensor_topic, average_temp)
    mqtt_client.publish(mqtt_hum_sensor_topic, average_hum)
    print("Sending: " + str(average_temp) + '°C and ' + str(average_hum) + '%')
    temp_storage.clear()
    hum_storage.clear()


mqtt_prefix = mqtt_client_name + '/sensor/'
mqtt_availability_topic = mqtt_prefix + 'availability'
mqtt_temp_sensor_topic = mqtt_prefix + 'temperature/state'
mqtt_hum_sensor_topic = mqtt_prefix + 'humidity/state'
temp_storage = []
hum_storage = []
last_measurement_sent = datetime.datetime.now()
raw_data_file = open('/home/pi/temp-hum-sensor-raw_temp.txt', 'a+')

def main():
    global startup_readings
    global last_measurement_sent

    mqtt_client = mqtt.Client(mqtt_client_name)
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.username_pw_set(mqtt_user, mqtt_pass)
    mqtt_client.will_set(mqtt_availability_topic, 'offline', retain=True)

    mqtt_client.connect(mqtt_host, mqtt_port)
    mqtt_client.loop_start()

    while True:
        humidity, temperature = get_sensor_values()

        if startup_readings == 0:
            compute_temp(temperature)
            compute_huminity(humidity)
            raw_data_file.write("%s;%s;%s\n" % (str(datetime.datetime.now()), str(temperature), str(humidity)))

            if last_measurement_sent < datetime.datetime.now() - send_interval:
                last_measurement_sent = datetime.datetime.now()
                send_measurements(mqtt_client)

        else:
            # Skip the first readings to get the sensor running
            startup_readings = startup_readings - 1
            print('Take values in ' + str(startup_readings) + ' readings.')


if __name__ == '__main__':
    main()
