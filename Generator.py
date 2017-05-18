from __future__ import print_function
import visa
import time

#open connection
rm = visa.ResourceManager('@py')
#important to include '@py' so that it will use "pyvisa-py" backend
#because ni-visa won't work on ARM based devices like the pi
'''
inst_list = rm.list_resources() #This throws a "Resource not available" or "the device has no langid" error
#not sure how to fix and it's really not a priority"
print(inst_list)
input_choice = input("Type the index of the desired instrument: ")
inst = rm.open_resource(inst_list[input_choice])
'''

print("INFO: type 'print errors' to dump errors to screen, and 'quit' to exit the program")
print("INFO: type 'q ' before queries")
inst = rm.open_resource('TCPIP::K-33511B-03176.local::inst0::INSTR')
command = ''
while command != 'quit':
	command = raw_input("Enter a command: ")
	if command != 'quit':
		#choose to query or write
		if command[0:2] == 'q ':
			command = command.strip('q ')
			inst.write(command)
			time.sleep(.05) # without delay read comes too early and causes error -420
			print(inst.read(),end='')
		elif command == 'print errors': #quick command to dump all errors in memory
			for i in range(50):
				inst.write('system:error?')
				time.sleep(.01)
				error = inst.read()
				print(error,end='')
				if error[0:2] == '+0':
					break
		elif command[0:4] == 'transfer':
			z = [(i-1)/100 for i in range(100)]
			inst.query_binary_values('sour:data:arb testarb',z,true)
		else:
			inst.write(command)

#close connection
inst.write('disp:text:clear')
inst.close()
print('closed instrument connection')
