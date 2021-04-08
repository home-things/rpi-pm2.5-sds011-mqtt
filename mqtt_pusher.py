#!/usr/bin/python3 -u
# coding=utf-8
# "DATASHEET": http://cl.ly/ekot
# https://gist.github.com/kadamski/92653913a53baf9dd1a8
#from __future__ import print_function
import serial, struct, sys, time, json, codecs #, subprocess
import paho.mqtt.client as mqtt
from pprint import pprint

DEBUG = False
CMD_MODE = 2
CMD_QUERY_DATA = 4
CMD_DEVICE_ID = 5
CMD_SLEEP = 6
CMD_FIRMWARE = 7
CMD_WORKING_PERIOD = 8
MODE_ACTIVE = 0
MODE_QUERY = 1
PERIOD_CONTINUOUS = 0
CRC_MAX = 256

# Hey, If you don't want to fork it, let's create env variable config
MQTT_HOST = '192.168.1.68' # 'rpi4.local'

MQTT_TOPIC = '/bedroom/weather/pm'

ser = serial.Serial()
ser.port = "/dev/ttyUSB0"
ser.baudrate = 9600
ser.timeout = 3

ser.open()
ser.flushInput()

byte, data = 0, ""


print("[mqtt] initing...")
mqttc = mqtt.Client(client_id = MQTT_TOPIC, clean_session = False)


def now():
    return datetime.now()

def now_minute():
    return now().replace(second=0, microsecond=0)


def dump(d, prefix=''):
    print(prefix + ' '.join(str(x) if type(x) == int else codecs.encode(x.encode('utf8'), 'hex').decode('ascii') for x in d))
    #codecs.encode(x, 'hex').encode('binascii')
    #pprint(codecs.encode(d[0].encode('utf8'), 'hex'))
    

def construct_command(cmd, data=[]):
    assert len(data) <= 12
    data += [0,]*(12-len(data))
    checksum = (sum(data)+cmd-2)%256
    ret = "\xaa\xb4" + chr(cmd)
    ret += ''.join(chr(x) for x in data)
    ret += "\xff\xff" + chr(checksum) + "\xab"

    if DEBUG:
        dump(ret, '> ')
    return ret.encode()

def process_data(d):
    r = struct.unpack('<HHxxBB', d[2:])
    pm2_5 = r[0]/10.0
    pm10 = r[1]/10.0
    #checksum = sum(ord(v) for v in d[2:8])%256
    checksum = sum(v for v in d[2:8])
    if checksum % CRC_MAX == d[8]:
        print('process data', r, pm2_5, pm10)
        # TODO: verify checksum
        return [pm2_5, pm10]
    else:
        print('process data', 'CRC=NOK', checksum, d[8], [pm2_5, pm10])

def process_version(d):
    r = struct.unpack('<BBBHBB', d[3:])
    #checksum = sum(ord(v) for v in d[2:8])%256
    checksum = sum(v for v in d[2:8]) % CRC_MAX
    print("Y: {}, M: {}, D: {}, ID: {}, CRC={}".format(r[0], r[1], r[2], hex(r[3]), "OK" if (checksum==r[4] and r[5]==0xab) else "NOK"))
    if checksum != r[4]:
        print('NOK:', checksum, r[4])

def read_response():
    if DEBUG:
        print('in buffer', ser.in_waiting, 'out buffer', ser.out_waiting)
    ser.flush()
    ser.flushInput()
    if DEBUG:
        print('in buffer', ser.in_waiting, 'out buffer', ser.out_waiting)
    byte = 0
    while byte != b"\xaa":
        byte = ser.read(size=1)
        if DEBUG:
            print('<skip:', byte)

    d = ser.read(size=9)

    if DEBUG:
        dump(d, '< ')
    return byte + d

def cmd_set_mode(mode=MODE_QUERY):
    ser.write(construct_command(CMD_MODE, [0x1, mode]))
    read_response()

def cmd_query_data():
    ser.write(construct_command(CMD_QUERY_DATA))
    d = read_response()
    if DEBUG:
        print('resp')
        pprint(d[1])
    values = []
    if d[1] == 192: #b"\xc0":
        values = process_data(d)
    return values

def cmd_set_sleep(sleep):
    mode = 0 if sleep else 1
    ser.write(construct_command(CMD_SLEEP, [0x1, mode]))
    read_response()

def cmd_set_working_period(period):
    ser.write(construct_command(CMD_WORKING_PERIOD, [0x1, period]))
    read_response()

def cmd_firmware_ver():
    print("checking version")
    ser.flushInput()
    ser.write(construct_command(CMD_FIRMWARE))
    d = read_response()
    process_version(d)

def cmd_set_id(id):
    id_h = (id>>8) % 256
    id_l = id % 256
    ser.write(construct_command(CMD_DEVICE_ID, [0]*10+[id_l, id_h]))
    read_response()

def pub_mqtt(jsonrow):
    #cmd = ['mosquitto_pub', '-h', MQTT_HOST, '-t', MQTT_TOPIC, '-s']
    #print('Publishing using:', cmd)
    #with subprocess.Popen(cmd, shell=False, bufsize=0, stdin=subprocess.PIPE).stdin as f:
    #    json.dump(jsonrow, f)
    mqttc.publish(MQTT_TOPIC, json.dumps(jsonrow), retain=True)

def on_connect(mqttc, userdata, flags, rc):
    global is_mqtt_connected

    print("Connected to mqtt with result code "+str(rc))
    #print(f"[mqtt] subscribing... {MQTT_TOPIC_CMD}")
    #mqttc.subscribe(MQTT_TOPIC_CMD)
    #mqttc.subscribe(MQTT_TOPIC_SW_CMD)
    #print("[mqtt] subscribed")
    is_mqtt_connected = True

mqttc.enable_logger(logger=None)
mqttc.on_connect = on_connect
#mqttc.on_message = on_message
print("[mqtt] connecting...")
mqttc.connect(MQTT_HOST)

# mqttc.loop_forever()
mqttc.loop_start() # loop thread

if __name__ == "__main__":
    print("start sds011 loopback...")

    cmd_set_sleep(0)
    print("initialize sds011...")
    cmd_firmware_ver()
    cmd_set_working_period(PERIOD_CONTINUOUS)
    cmd_set_mode(MODE_QUERY)
    print("sds011 initialized!")
    skip_vals = 3 if not DEBUG else 1
    result_values = None

    while True:
        if not is_mqtt_connected: continue 
        try:
            cmd_set_sleep(0)
            for t in range(skip_vals):
                values = cmd_query_data();
                if DEBUG:
                    print('values', values, 't', t, '/', skip_vals)
                if values is not None and len(values) == 2:
                    result_values = values
                    print("skip: PM2.5: ", values[0], ", PM10: ", values[1])
                    time.sleep(2)

            if result_values:
                print('sending...')

                ## open stored data
                #try:
                #    with open(JSON_FILE) as json_data:
                #        data = json.load(json_data)
                #except IOError as e:
                #    data = []

                ## check if length is more than 100 and delete first element
                #if len(data) > 100:
                #    data.pop(0)

                # append new values
                jsonrow = {'pm2_5': result_values[0], 'pm10': result_values[1], 'time': time.strftime("%d.%m.%Y %H:%M:%S")}
                #data.append(jsonrow)

                ## save it
                #with open(JSON_FILE, 'w') as outfile:
                #    json.dump(data, outfile)

                if MQTT_HOST != '':
                    print(jsonrow)
                    pub_mqtt(jsonrow)
                    
            else:
                print('reading is failed')
            print("Going to sleep for a while...")
            cmd_set_sleep(1)
            time.sleep(60 if result_values else 1)
        except:
            time.sleep(60 if result_values else 1)
            continue
