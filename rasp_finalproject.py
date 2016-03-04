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
data_alllimit = "0"
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

	# Insert if outlet_id first contact
	if(check_id  == 1):	
		elec_limit = 0
		elec_outletname = "Unknown"
		c.execute("INSERT INTO electricpower (outlet_id, outlet_name, elec_limit) VALUES (%s,%s,%s)",(outlet_id, elec_outletname, elec_limit))
		db.commit()	
		print("ok")
	check_id  = 0

	# Update power every 5 min
	c.execute("UPDATE electricpower SET elec_power=%s WHERE outlet_id=%s ",(unit, outlet_id))
	db.commit()

	# Select limit from database
	c.execute("SELECT outlet_id, elec_limit, elec_power FROM electricpower")
	check_led_power = 0.0
	check_led_limit = 0
	for row in c.fetchall() :
		# Data from rows
		data_idoutlet = str(row[0])
		data_limit = str(row[1])
		data_power = str(row[2])

		print("ID: "+data_idoutlet+" limit: "+data_limit+" unit: "+data_power)
		# Change variable 
		data_idoutlet_int = (int)(data_idoutlet)
		data_limit_int = (int)(data_limit)
		data_power_float = (float)(data_power)		
		# Check limit LED
		
		if(data_idoutlet_int != 0):
			check_led_power = check_led_power + data_power_float
			#check_led_limit = check_led_limit + data_limit_int

			limit_str = "%4s%8s%s" % (data_idoutlet, data_limit, data_alllimit)
			print ("sent client"+limit_str)
			#send	
			radio.stopListening();
			message = list(limit_str)
			radio.write(message)
			print ("We sent the message of{}".format(message))
			radio.startListening()
			time.sleep(1)

	c.execute("SELECT elec_limit FROM electricpower WHERE outlet_id = 0")
	for row in c.fetchall() :
		# Data from rows
		data_alloutlet_limit = str(row[0])
		check_led_limit  = (int)(data_alloutlet_limit)
		
	if(check_led_power < check_led_limit or check_led_limit == 0):
		GPIO.output(22,GPIO.LOW)
		GPIO.output(24,GPIO.LOW)
		GPIO.output(23,GPIO.HIGH)
		data_alllimit = "0"
	if(check_led_power >= (check_led_limit-50) and check_led_limit != 0):
		GPIO.output(23,GPIO.LOW)
		GPIO.output(22,GPIO.LOW)
		GPIO.output(24,GPIO.HIGH)
		data_alllimit = "0"
	if(check_led_power >= check_led_limit and check_led_limit != 0):
		GPIO.output(22, GPIO.HIGH)
		GPIO.output(23,GPIO.LOW)
		GPIO.output(24,GPIO.LOW)
		data_alllimit = "1"

	all_power = str(check_led_power)
	all_limit = str(check_led_limit)

	# Insert All unit 
	check_id = 1
	alloutlet_id = 0
	alloutlet_name = "All Outlet"
	c.execute("SELECT outlet_id FROM electricpower")	
	for row in c.fetchall() :
		# Data from rows
		data_id = str(row[0])
		# Change variable
		data_id_int = (int)(data_id )
		# Check outlet_id is first or not
		if(data_id_int == alloutlet_id):
			check_id  += 1	

	# Insert if outlet_id first contact
	if(check_id  == 1):
		alloutlet_limit = 0
		c.execute("INSERT INTO electricpower (outlet_id, outlet_name, elec_power, elec_limit) VALUES (%s,%s,%s,%s)",(alloutlet_id, alloutlet_name, all_power, alloutlet_limit))
		db.commit()
	check_id  = 0

	c.execute("UPDATE electricpower SET elec_power=%s WHERE outlet_id=0 ",(all_power))
	db.commit()

	print ("All Unit: "+all_power+" All Limit: "+all_limit)
	# LCD show status

	lcd = lcddriver.lcd()

	lcd.lcd_display_string("Sum Unit: "+all_power, 1)
	lcd.lcd_display_string("Sum Limit: "+all_limit+"", 2)

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