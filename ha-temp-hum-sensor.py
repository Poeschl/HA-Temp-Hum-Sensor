#!/usr/bin/python
import datetime
import time

import Adafruit_DHT
import paho.mqtt.client as mqtt
import yaml

log_out_flag = False

sensor = Adafruit_DHT.DHT22
startup_readings = 3

smoothing_alpha = 0.25


def get_sensor_values():
    time.sleep(5)
    return Adafruit_DHT.read_retry(sensor, pin)


def collect_temp(temp):
    if temp is not None and -20 < temp < 40:
        temp_storage.append(temp)
    else:
        print('Ignoring temp: ' + str(temp))


def collect_huminity(hum):
    if hum is not None and 0 < hum < 100:
        hum_storage.append(hum)
    else:
        print('Ignoring hum: ' + str(hum))


def exponential_smoothing(current_value, last_value):
    return smoothing_alpha * current_value + (1 - smoothing_alpha) * last_value


def calc_average(array):
    sum = 0
    for elem in array:
        sum = sum + elem
    return round(sum / len(array), 1)


def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        print('Connected to broker({0}).'.format(str(mqtt_host)))
        send_ha_autodiscovery(client)
        print('Sent autodiscovery for HA')
    else:
        print('Not connect to broker({0}). Errorcode: {1}'.format(str(mqtt_host), str(rc)))


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
    ha_discover_content_invalid = '{"name":"%s Invalid measurements",' \
                                  '"state_topic": "%s", \
                                   "availability_topic":"%s"}' % (mqtt_client_name, mqtt_invalid_sensor_topic, mqtt_availability_topic)

    temp_topic = ha_discover_topic_template % (mqtt_client_name, 'temperature')
    hum_topic = ha_discover_topic_template % (mqtt_client_name, 'humidity')
    invalid_topic = ha_discover_topic_template % (mqtt_client_name, 'invalid')

    mqtt_client.publish(mqtt_availability_topic, 'online', retain=True)
    mqtt_client.publish(temp_topic, ha_discover_content_temp, retain=True)
    mqtt_client.publish(hum_topic, ha_discover_content_hum, retain=True)
    mqtt_client.publish(invalid_topic, ha_discover_content_invalid, retain=True)


def send_measurements(mqtt_client):
    global temp_storage, hum_storage, last_temp, last_hum, invalid_measure_count

    average_temp = calc_average(temp_storage)
    average_hum = calc_average(hum_storage)

    if last_temp is None:
        filtered_temp = average_temp
    else:
        filtered_temp = exponential_smoothing(average_temp, last_temp)

    if last_hum is None:
        filtered_hum = average_hum
    else:
        filtered_hum = exponential_smoothing(average_hum, last_hum)

    mqtt_client.publish(mqtt_temp_sensor_topic, filtered_temp)
    mqtt_client.publish(mqtt_hum_sensor_topic, filtered_hum)
    mqtt_client.publish(mqtt_invalid_sensor_topic, invalid_measure_count)

    print("Sending: " + str(average_temp) + '°C and ' + str(average_hum) + '%')
    if log_out_flag:
        filtered_data_file.write("%s;%s;%s\n" % (str(datetime.datetime.now()), str(filtered_temp), str(filtered_hum)))
        filtered_data_file.flush()

    temp_storage.clear()
    hum_storage.clear()
    last_temp = filtered_temp
    last_hum = filtered_hum
    invalid_measure_count = 0


def parse_config():
    global send_interval, pin, mqtt_client_name, mqtt_host, mqtt_port, mqtt_user, mqtt_pass, mqtt_prefix, mqtt_availability_topic, \
        mqtt_temp_sensor_topic, mqtt_hum_sensor_topic, mqtt_invalid_sensor_topic

    with open('config.yaml') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

        send_interval = datetime.timedelta(minutes=config['send_interval'])
        pin = config['pin']
        mqtt_client_name = config['mqtt']['client']
        mqtt_host = config['mqtt']['host']
        mqtt_port = config['mqtt']['port']
        mqtt_user = config['mqtt']['user']
        mqtt_pass = config['mqtt']['pass']

    mqtt_prefix = mqtt_client_name + '/sensor/'
    mqtt_availability_topic = mqtt_prefix + 'availability'
    mqtt_temp_sensor_topic = mqtt_prefix + 'temperature/state'
    mqtt_hum_sensor_topic = mqtt_prefix + 'humidity/state'
    mqtt_invalid_sensor_topic = mqtt_prefix + 'invalid/state'


send_interval = None
pin = None
mqtt_client_name = None
mqtt_host = None
mqtt_port = None
mqtt_user = None
mqtt_pass = None
mqtt_prefix = None
mqtt_availability_topic = None
mqtt_temp_sensor_topic = None
mqtt_hum_sensor_topic = None
mqtt_invalid_sensor_topic = None

temp_storage = []
hum_storage = []
last_temp = None
last_hum = None
last_measurement_sent = datetime.datetime.now()
invalid_measure_count = 0

if log_out_flag:
    raw_data_file = open('/home/pi/temp-hum-sensor-raw.csv', 'a+')
    filtered_data_file = open('/home/pi/temp-hum-sensor-filtered.csv', 'a+')


def main():
    global startup_readings, last_measurement_sent, invalid_measure_count

    parse_config()

    mqtt_client = mqtt.Client(mqtt_client_name)
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.username_pw_set(mqtt_user, mqtt_pass)
    mqtt_client.will_set(mqtt_availability_topic, 'offline', retain=True)

    mqtt_client.connect(mqtt_host, mqtt_port)
    mqtt_client.loop_start()

    while True:
        humidity, temperature = get_sensor_values()

        if startup_readings == 0:
            collect_temp(temperature)
            collect_huminity(humidity)
            if log_out_flag:
                raw_data_file.write("%s;%s;%s\n" % (str(datetime.datetime.now()), str(temperature), str(humidity)))
                raw_data_file.flush()
            if humidity is None or temperature is None:
                invalid_measure_count = invalid_measure_count + 1

            if last_measurement_sent < datetime.datetime.now() - send_interval:
                last_measurement_sent = datetime.datetime.now()
                send_measurements(mqtt_client)

        else:
            # Skip the first readings to get the sensor running
            startup_readings = startup_readings - 1
            print('Take values in ' + str(startup_readings) + ' readings.')


if __name__ == '__main__':
    main()
