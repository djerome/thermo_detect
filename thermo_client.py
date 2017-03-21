#!local/bin/python

import os
import socket
import time
import json
import requests
import smbus

#initializations
thermo1 = 'cranberry'
thermo2 = 'strawberry'
onewire = 'DS18B20+'
i2c = 'TCN75A'
thermo_clients = {thermo1: [onewire], thermo2: [onewire, i2c]}
thermo_server = 'cranberry'
port = '5002'
url = 'http://' + thermo_server + ':' + port + '/thermo/api/temp'
headers = {'Content-Type': 'application/json'}
sample_time = 60

sensors = {
'28-00000530a030': {'location': 'living room', 'host': thermo1, 'type': onewire},
'28-00000530bf48': {'location': 'office', 'host': thermo1, 'type': onewire},
'28-0000053125f9': {'location': 'mechanical room', 'host': thermo1, 'type': onewire},
'28-00000531341c': {'location': 'front porch', 'host': thermo1, 'type': onewire},
'28-0000073ce982': {'location': 'cold room', 'host': thermo1, 'type': onewire},
'28-00000531004f': {'location': 'garage inside', 'host': thermo2, 'type': onewire},
'28-041693d731ff': {'location': 'garage outside', 'host': thermo2, 'type': onewire},
'72': {'location': 'basement stairs', 'host': thermo2, 'type': i2c},
}

def temp_raw(sensor):
	f = open(sensor, 'r')
	lines = f.readlines()
	f.close()
	return lines

def read_temp(sensor):
	lines = temp_raw(sensor)
	while lines[0].strip()[-3:] != 'YES':
		time.sleep(0.2)
		lines = temp_raw()

	temp_output = lines[1].find('t=')
	if temp_output != -1:
		temp_string = lines[1].strip()[temp_output+2:]
		temp_c = float(temp_string) / 1000.0
		return temp_c
	else:
		print 'Sensor ' + sensor + ' in error'
		return 999

hostname = socket.gethostname()
sensor_types = thermo_clients[hostname]

# prep to read from sensors
for sensor_type in sensor_types:

	# prep to read 1wire sensors
	if sensor_type == onewire:
		os.system('modprobe w1-gpio')
		os.system('modprobe w1-therm')
		time.sleep(15)

	# prep to read i2c sensors
	elif sensor_type == i2c:
		bus = smbus.SMBus(1)
		#Device address
		device_add = 72 # CHANGE THIS TO YOUR DEVICE ADDRESS

		# Index of the register on the TCN75A which contains the configurable
		# resolution settings (temp_res)
		config_reg = 1

		# Temperature resolution
		# Possible values are 0, 32, 64, and 96, where
		# 0 is lowest resolution and 96 is the highest.
		# 96 = 0.01625C steps
		# 0  = 0.5C steps (default)
		temp_res = 96

		# Index of register where current temperature is stored
		temp_reg = 0

	else:
		print 'Invalid sensor type ' + sensor_type
		exit(1)

while True:
	for sensor_id, sensor_info in sensors.iteritems():

		# if the sensor is on this host
		if sensor_info['host'] == hostname:

			# read the temp off a 1wire sensor
			if sensor_info['type'] == onewire:
				sensor = '/sys/bus/w1/devices/' + sensor_id + '/w1_slave'
				temperature = read_temp(sensor)

			# read the temp off a i2c sensor
			elif sensor_info['type'] == i2c:
				try:
					# Configure sensor resolution
					bus.write_byte_data(device_add, config_reg, temp_res)

					bus.write_byte(device_add, temp_reg)

					# Read 2 bytes from temperature register
					temperature_bytes = bus.read_i2c_block_data(device_add, temp_reg, 2)

					# Byte 0 contains integer part of temperature value
					# Byte 1 contains decimal part which is 1/256 of a degrees celsius
					# Values 1-127 are positive and values greater than 127 are negative
					# following shows temperature values based on received bytes:
					# [1][0]=1C,[0][16]=0.062C, [0][0]=0C, [255][240]=-0.062 C,[255][0]=-1C
					temperature = temperature_bytes[0] + temperature_bytes[1]/256.000;
					if temperature > 127:
						temperature = temperature - 256.000

				except IOError as (errno, strerror):
					print "I/O error({0}): {1}".format(errno, strerror)
			else:
				print 'Invalid sensor type ' + sensor_type
				exit(1)

			# assemble sample dict
			sample = {'id': sensor_id, 'timestamp': time.time(), 'temp': temperature}
			print 'sample = ' + str(sample)

			# send sample to temperature server
			try:
				r = requests.post(url, data=json.dumps(sample), headers=headers)
			except:
#				abort(503)
				print "Error posting: " + str(sample)

		else:
			print 'Sensor ' + sensor_id + ' not configured on this host'

	# wait until next sample
	time.sleep(sample_time)
