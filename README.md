# rpi-pm2.5-sds011-mqtt
AirQuality PM2.5 SDS011 Raspberry Pi Python3 MQTT publisher

# Home Assistant configuration
```yaml
sensor:
  # SDS011 at bedroom
  - platform: mqtt
    name: "AirQuality PM2.5 Bedroom"
    state_topic: "/bedroom/weather/pm"
    unit_of_measurement: "µg/m³"
    value_template: "{{ value_json.pm2_5 }}"
  - platform: mqtt
    name: "AirQuality PM10 Bedroom"
    state_topic: "/bedroom/weather/pm"
    unit_of_measurement: "µg/m³"
    value_template: "{{ value_json.pm10 }}"
```
docs: https://www.home-assistant.io/integrations/sensor.mqtt/

todo: use ha auto-config mqtt topics:
`homeassistant/sensor/airquality_bedroom/pm2_5/config`
`homeassistant/sensor/airquality_bedroom/pm10/config`

# Why sds011
It's the best cheap air particles sensor

# Thanks
https://github.com/zefanja/aqi


----


![photo_2021-02-10_21-43-39](https://user-images.githubusercontent.com/6201068/107556188-25c2af80-6be9-11eb-966e-0cc1ef88e148.jpg)
