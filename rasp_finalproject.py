#!/usr/bin/python
import MySQLdb
import datetime
import RPi.GPIO as GPIO
from lib_nrf24 import NRF24
import time
import smbus
import spidev
import lcddriver

	# Function LED
def setting():
	GPIO.setmode (GPIO.BCM)
	# 22 RED
	# 23 GREEN
	# 24 BLUE
	GPIO.setup(22,GPIO.OUT)
	GPIO.setup(23,GPIO.OUT)
	GPIO.setup(24,GPIO.OUT)

setting()



# Set link
pipes = [[0xe7, 0xe7, 0xe7, 0xe7, 0xe7], [0xc2, 0xc2, 0xc2, 0xc2, 0xc2]]

radio = NRF24(GPIO, spidev.SpiDev())
radio.begin (0, 17)
radio.setPayloadSize(60)
radio.setChannel (0x60)

radio.setDataRate(NRF24.BR_2MBPS)
radio.setPALevel(NRF24.PA_MIN)
radio.setAutoAck(True)
radio.enableDynamicPayloads()
radio.enableAckPayload()
radio.openWritingPipe(pipes[1]);
radio.openReadingPipe(1, pipes[0])
radio.printDetails()

radio.startListening()


# Open database connection
db = MySQLdb.connect(host="localhost", user="root", passwd="devilsecret", db="electricpower")	
# Start loop send and recev
date_time_data = ""
data_outlet_id = ""
while(True):
	ackPL = [1]
	while  not radio.available(0):
		time.sleep(1/10000)
	#set cursor database	
	c = db.cursor()

	#LCD show start

	#receive
	receivedMessage = []
	radio.read(receivedMessage, radio.getDynamicPayloadSize())

	date = time.strftime("%Y-%m-%d")
	clock = time.strftime("%H:%M:00")
	date_time = time.strftime("%Y-%m-%d %H:%M:00")
	count = 0
	outlet_id = ""
	unit = ""
	watt = ""
	checkchar = 0
	for n in receivedMessage:
		# frame format header
		if(n >=32 and n <=126):
			#4 char
			if(checkchar <= 4):
				outlet_id += chr(n)
			#5 char	
			if(checkchar >= 5 and checkchar <= 13):
				unit += chr(n)
			#5 char	
			if(checkchar >= 14 and checkchar <= 22):
				watt += chr(n)

			checkchar = checkchar+1

	radio.writeAckPayload(1, ackPL, len(ackPL))
	print("Loaded payload reply of {}".format(ackPL))		
	print(outlet_id + unit + watt)
	# Check outlet_id
	check_id = 1
	# Select database
	c.execute("SELECT outlet_id FROM electricpower")	
	for row in c.fetchall() :
		# Data from rows
		data_id = str(row[0])
		# Change variable
		data_id_int = (int)(data_id )
		outlet_id_int = (int)(outlet_id)
		# Check outlet_id is first or not
		if(data_id_int == outlet_id_int):
			check_id  += 1	

	if(check_id  == 1):
		# Insert if outlet_id first contact
		elec_limit = 0
		c.execute("INSERT INTO electricpower (outlet_id, elec_limit) VALUES (%s,%s)",(outlet_id, elec_limit))
		db.commit()	
		print("ok")
	check_id  = 0

	# update power every 5 min
	c.execute("UPDATE electricpower SET elec_power=%s WHERE outlet_id=%s ",(unit, outlet_id))
	db.commit()

	# Select limit from database
	c.execute("SELECT outlet_id, elec_limit, elec_power FROM electricpower")
	check_led_power = 0
	check_led_limit = 0
	for row in c.fetchall() :
		# Data from rows
		data_idoutlet = str(row[0])
		data_limit = str(row[1])
		data_power = str(row[2])

		print("ID: "+data_idoutlet+" limit: "+data_limit+" unit: "+data_power)
		# Change variable 
		data_limit_int = (int)(data_limit)
		data_power_float = (float)(data_power)
		data_power_int = (int)(data_power_float)
		# Check limit LED
		
		check_led_power = check_led_power + data_power_int
		check_led_limit = check_led_limit + data_limit_int

		limit_str = "%4s%8s" % (data_idoutlet, data_limit)
		print limit_str
		#send	
		radio.stopListening();
		message = list(limit_str)
		radio.write(message)
		print ("We sent the message of{}".format(message))
		radio.startListening()
		time.sleep(1)

	if(check_led_power < check_led_limit):
		GPIO.output(22,GPIO.LOW)
		GPIO.output(23,GPIO.HIGH)
	if(check_led_power >= (check_led_limit-50) and check_led_limit != 0):
		GPIO.output(22, GPIO.HIGH)
		GPIO.output(23,GPIO.HIGH)
	if(check_led_power >= check_led_limit and check_led_limit != 0):
		GPIO.output(22, GPIO.HIGH)
		GPIO.output(23,GPIO.LOW)

	all_power = str(check_led_power)
	all_limit = str(check_led_limit)

	print ("All Unit: "+all_power+" All Limit: "+all_limit)
	# LCD show status

	lcd = lcddriver.lcd()

	lcd.lcd_display_string("All Unit:  "+all_power, 1)
	lcd.lcd_display_string("All Limit: "+all_limit+"", 2)

	check_outlet_id = 1
	c.execute("SELECT outlet_id, date_time FROM electricpower.electricdata")
	for row in c.fetchall() :
		# Data from rows
		data_outlet_id = str(row[0])
		date_time_data = str(row[1])
		print ("Date Outlet ID: "+data_outlet_id)

		data_id_int = (int)(data_outlet_id)
		outlet_id_int = (int)(outlet_id)

		if(date_time_data == date_time):
			if(data_id_int == outlet_id_int):
				check_outlet_id = 2

	stroutlet = (str)(check_outlet_id)

	print ("Date Time: "+date_time)
	print ("Date Time Data: "+date_time_data)
	print (stroutlet)
	# Insert electricdata date/time/watt/unit
	if(date_time_data != date_time or check_outlet_id == 1):
		c.execute("INSERT INTO electricpower.electricdata (id, outlet_id, date_time, watt, unit) VALUES (null,%s,%s,%s,%s)",(outlet_id, date_time, watt, unit))
		db.commit()	
		print("OK Insert electricdata")
	check_outlet_id = 0
