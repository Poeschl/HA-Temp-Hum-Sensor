# Homeassistant Temperature and Humidity Sensor

This script is a python daemon that runs in background on my snips satellite Pi Zero
 and transmits temperature and humidity to my Home Assistant instance.

As sensor for the values a `AM2301` sensor is used which has the same api like the `DHT22`.

# systemd install

A service file for systemd is provided in the repro to start and run it in the background.
Just adjust the location of the script file and the config inside the script and you are good to go.
