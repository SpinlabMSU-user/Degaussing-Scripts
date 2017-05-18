from __future__ import print_function
import linecache
import math
import numpy as np
import random
import RPi.GPIO as GPIO
import sys
import time
#import usb # I think this library is unnecessary
import visa

# input is raw_input in python 2.7
input_choice = str(raw_input("Do you want to use file or terminal input? (f/t) (or quit)\n"))

#Declare some variables
GPIO_list = []
coil_list = []
f,N,V0 = 10,10,5 #Default values

# Take in input file and sets appropriate parameters
if input_choice == 'f':
	file_input = open('Degaussing.txt','r')
	for i, line in enumerate(file_input):
		#Read the GPIO pins to be used
		if line == '# GPIO pin numbers\n':
			# linecache.getline() opens the file itself, doesn't need file already opened
			# so with standardized file format the file wouldn't need to be opened first
			GPIO_input = linecache.getline('Degaussing.txt', i+2)
			GPIO_input = GPIO_input.strip()
			GPIO_list = GPIO_input.split(',')
			# convert the strings of numbers to integers
			GPIO_list = [int(i) for i in GPIO_list]
			print('Selected GPIO pins: ',GPIO_list)
		#Read the Coil order
		elif line == '# Coil order\n':
			coil_input = linecache.getline('Degaussing.txt', i+2)
			for coil in coil_input.strip():
				coil_list.append(coil)
			print('Selected coil order: ',coil_list)
		#Read the time to put current through each coil
		elif line[0:15] == '# Coil duration':
			sleep_time = float(linecache.getline('Degaussing.txt', i+2))
			print('Pause interval: ',sleep_time)
		#Read the instrument ID, 
		elif line == '# Instrument ID\n':
			rm = visa.ResourceManager('@py')
			inst_choice = linecache.getline('Degaussing.txt', i+2)
			inst_choice = inst_choice.rstrip('\n')
			inst = rm.open_resource(inst_choice)
			print(inst_choice)
		elif line == '# SCPI command list\n':
			file_input.next() # moves file read point one line after current point
			for line in file_input:
				command = line.rstrip('\n')
				print(command)
				inst.write(command)
			inst.write('DISP:TEXT "Instrument Parameters are set"')
			# TODO add a check to continue statement
			# TODO add file input for wave parameters

if input_choice == 'quit':
	sys.exit()

# Set parameters of waveform
if input_choice == 't':
	V0 = float(raw_input("Initial Voltage Amplitude (less than 10V): "))
	dV = int(raw_input("Number of digits past decimal for voltages (precision): "))
	sample_rate = float(raw_input("Sample rate (Samples/s): "))
	f = float(raw_input("Frequency (Hz): "))
	duration = float(raw_input("Duration (s): "))
	t = np.linspace(0,duration,sample_rate*N)
	data = np.around((-t/duration+1)*np.sin(2*np.pi*f*t),dV)
	#The points need to be between -1 and 1, and scaled later
	#so V0 is used in the data sending section
	#print(data)

### Activate the selected pins of the pi
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# GPIO pin numbers are requested if in terminal input mode
if input_choice == 't':
	GPIO_input = str(raw_input('Select GPIO pins by entering comma separated list (or enter default):\n'))
	if GPIO_input == "default":
		GPIO_list = [17,27,22,23]
	else:
		GPIO_list = GPIO_input.split(',') ## What if invalid input? There is no custom error handling
	# TODO: add "try: except" statement in here
	GPIO_list = [int(i) for i in GPIO_list]

# Initialize selected GPIO pins
for i in GPIO_list:
	GPIO.setup(i,GPIO.OUT)
	GPIO.output(i,GPIO.HIGH) #Because relays are "Active Low"

### Set coil order and duration
if input_choice == 't':
	print('Enter Coil Order (names are x,y,z,c):')
	coils = list(raw_input())
	coil_list = []
	for coil in coils:
		if coil in "xyzcXYZC":
			coil_list.append(coil)

### Connection to the instrument is established and waveform is set up
rm = visa.ResourceManager('@py')
#important to include '@py' so that "pyvisa-py" backend will be used
#because ni-visa won't work on ARM based devices like the pi
if input_choice == 't':
	try:
        	##TODO: Move the connection part to before user input
			#and modify so that if connection fails there
			#is a message indicating that it's not connected
			#or turned off instead of just crashing
			#with a prompt to try again.
		##TODO: Clear/reset generator immediately after connecting
		#Open Connection
        	rm = visa.ResourceManager('@py')
        	#LAN - VXI-11 Connection
        	inst = rm.open_resource("TCPIP::K-33511B-03176.local::inst0::INSTR")
	
        	#Set Timeout to 5 seconds
        	inst.timeout = 5000
	
        	#*IDN? - Query Instrument ID
		#inst.write("*RST")
		inst.write("*CLS")
		inst.write("*IDN?")
		print(inst.read())
	
		# Do stuff with instrument here
        
		command_list = [
		'func arb', #Set the function type to arb
		##TODO: Update the sample rate to match input
		'func:arb:srate '+str(sample_rate), #Set the sample rate of the data points
		'func:arb:filter normal', # Smooths the output
		'func:arb:ptpeak '+str(V0) # Sets the difference between max and min data points
		]
		
		#Create a string of the data points
		points = " ".join(str(i)+',' for i in data)
		points = points[:-1] #What is the function of this?
		#print(points)
		
		# Transfer and load data points
		command_list.extend((
		'data:arb wave,'+points, #Load arb into working memory
		'func:arb wave', #Select arb
        	'mmem:store:data "INT:\wave.arb"', #Save arb to drive
        	'data:vol:clear', # Clear working memory
        	'mmem:load:data "INT:\wave.arb"',
		'func arb', #Set function type to arb
        	'func:arb "INT:\wave.arb"')) #Set arb as sequence saved to drive
		
		# Set up Bursting mode
		command_list.extend((
		'burs:mode trig', # Set burst mode to trigger
		'burs:ncyc 1', # Sets number of cycles to be done in the burst
		'burs:int:per '+str(duration), #Set the period of the burst
		'burs:phase 0', # Select starting point (-2pi,2pi)
		'init:cont on', # Tells instrument to not return to wait-for-trigger state
		'trig:sour bus', # Set the trigger source as the remote interface
		'burs:state on'
		))
		
		# Execute commands and check for errors
        	for command in command_list:
        		inst.write(command)
        	        inst.write('system:error?')
        	        time.sleep(.01)
        	        error = inst.read()
			max_length = 50
			if len(command) > max_length:
				print(command[:max_length],' ... : ',error)
			else:
				print(command,' : ',error)
		
		
		### Relays are turned on for appropriate coils
		for coil in coil_list:
			if coil in ('x','X'):
				relay = GPIO_list[0]
			elif coil in ('y','Y'):
				relay = GPIO_list[1]
			elif coil in ('z','Z'):
				relay = GPIO_list[2]
			elif coil in ('c','C'):
				relay = GPIO_list[3]
			else:
				print('Invalid coil; check input')
				print(order_list)
				break
			GPIO.output(relay,GPIO.LOW)
			time.sleep(.5) #Delay to ensure that relay has time to respond and lock
			GPIO.output(relay,GPIO.HIGH) #Both high and low because relays only require a pulse
			inst.write("output on")
			inst.write("*TRG") #Trigger the burst
			progress_indication = 'Coil '+coil+' is having power transmitted to it'
			print(progress_indication)
			#inst.write('DISP:TEXT "'+progress_indication+'"')
			time.sleep(duration)
			GPIO.output(relay,GPIO.LOW)
			time.sleep(.5)
			GPIO.output(relay,GPIO.HIGH)
			inst.write("output off")
			time.sleep(.5) #Delay between switching
        	# Close instrument connection
		inst.write('*RST')
		inst.write('*CLS')
		inst.write('DISP:TEXT:CLEAR')
		inst.close()
        	print("closed instrument connection")
		
	except Exception as err:
	        print('Exception: ' + str(err.message))
	
	finally:
	        print('complete')
