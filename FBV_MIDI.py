#!/usr/bin/python

#FBV_MIDI.py
#Version 1.0
#7/29/18
#kevin.quann@gmail.com

#Working:
#-MIDI out, basic MIDI in
#-Tap tempo functionality
#-Works with POD HD Tuner
#-Expression pedals

#To Do:
#-Expand interface to work with Fractal/Kemper units
#-Test Program Change and other MIDI commands
#-Implement Function switch
#-Much more....

import serial
import time
import threading
import Queue
import mido
import struct
import sys
import getopt

#Defining some global variables:
Exp_vals = [0, 0] #Set list for two expression pedal values
Exp_1_state = False #initialize "Wah" as being off
Exp_2_state = False #initialize "Vol" as being off
Exp_1_users = [] #at init, no effects are using this
Exp_2_users = [] #at init, no effects are using this

start_time = time.time()
HD_readqueue = Queue.Queue(1000)
FBV_readqueue = Queue.Queue(1000)
MIDI_readqueue = Queue.Queue(1000)
Arduino_writequeue = Queue.Queue(1000)
Debug_queue = Queue.Queue(1000)

Current_page = 0
Wah_state = False # Wah is set off on init

Tap_last_pressed = 0 #Timestamp of last tap tempo press
Tap_intervals = [0, 0, 0] #This is variable to store last 3 tap intervals for averaging
Tap_index = 0 #this cycles through the Tap_intervals
Tap_time = 0.500 #initializes to 500ms
Tap_held = False #Is tap button being held?
Tuner_mode = False

#Function to initialize parameters based on FBV model
def Initialize_options(Serial_port, Model):
	global Arduino
	global Buttons
	global LEDs
	global Colors
	global LED_on
	global LED_off
	global LED_dim

	Arduino = serial.Serial(port=Serial_port, baudrate=115200)
	
	#Colors are only utilized for FBV3, will have no effect on FBV MkII
	Colors = ( 
	"\xf0\x03\x05\x20", #LED 0 (A)
	"\xf0\x03\x05\x30", #LED 1 (B)
	"\xf0\x03\x05\x40", #LED 2 (C)
	"\xf0\x03\x05\x50", #LED 3 (D)
	"\xf0\x03\x05\x02", #LED 4 (FS1)
	"\xf0\x03\x05\x12", #LED 5 (FS2)
	"\xf0\x03\x05\x41", #LED 6 (FS3)
	"\xf0\x03\x05\x51", #LED 7 (FS4)
	"\xf0\x03\x05\x21" #LED 8 (FS5)
	)


	if Model == "FBV3":
			
		#Remapping prefixes for FBV 3 in tuple
		Buttons = (
		"\xf0\x03\x81\x20", #BTN 0 (A)
		"\xf0\x03\x81\x30", #BTN 1 (B)
		"\xf0\x03\x81\x40", #BTN 2 (C)
		"\xf0\x03\x81\x50", #BTN 3 (D)
		"\xf0\x03\x81\x02", #BTN 4 (FS1)
		"\xf0\x03\x81\x12", #BTN 5 (FS2)
		"\xf0\x03\x81\x41", #BTN 6 (FS3)
		"\xf0\x03\x81\x51", #BTN 7 (FS4)
		"\xf0\x03\x81\x21", #BTN 8 (FS5)
		"\xf0\x03\x81\x61", #BTN 9 ("Tap tempo")
		"\xf0\x03\x81\x43", #BTN 10 (Toe switch)
		"\xf0\x03\x81\x10", #BTN 11 (Up arrow)
		"\xf0\x03\x81\x00", #BTN 12 (Down arrow)
		"\xf0\x03\x81\x01" #BTN 13 ("Function")
		)

		LEDs = (
		"\xf0\x03\x04\x20", #LED 0 (A)
		"\xf0\x03\x04\x30", #LED 1 (B)
		"\xf0\x03\x04\x40", #LED 2 (C)
		"\xf0\x03\x04\x50", #LED 3 (D)
		"\xf0\x03\x04\x02", #LED 4 (FS1)
		"\xf0\x03\x04\x12", #LED 5 (FS2)
		"\xf0\x03\x04\x41", #LED 6 (FS3)
		"\xf0\x03\x04\x51", #LED 7 (FS4)
		"\xf0\x03\x04\x21", #LED 8 (FS5)
		"\xf0\x03\x04\x61", #LED 9 ("Tap tempo")
		"\xf0\x03\x04\x13", #LED 10 (Wah)
		"\xf0\x03\x04\x03", #LED 11 (Volume)
		"\xf0\x03\x04\x01" #LED 12 ("Function") 
		)

		#LED state suffixes:
		LED_on = "\x01" #Bright for FBV3
		LED_off = "\x02" #Off for FBV3
		LED_dim = "\x00" #Dim for FBV3

	elif Model == "MkII":

		#Remapping prefixes for FBV Shortboard_MKII in tuple
		Buttons = (
		"\xf0\x03\x81\x20", #BTN 0 (FS5, "A")
		"\xf0\x03\x81\x30", #BTN 1 (FS6, "B")
		"\xf0\x03\x81\x40", #BTN 2 (FS7, "C")
		"\xf0\x03\x81\x50", #BTN 3 (FS8, "D")
		"\xf0\x03\x81\x00", #BTN 4 (Down arrow, serves as standard footswitch)
		"\xf0\x03\x81\x12", #BTN 5 (FS1, "Stomp")
		"\xf0\x03\x81\x41", #BTN 6 (FS2, "Mod")
		"\xf0\x03\x81\x51", #BTN 7 (FS3, "Delay")
		"\xf0\x03\x81\x21", #BTN 8 (FS4, "Reverb")
		"\xf0\x03\x81\x61", #BTN 9 ("Tap tempo")
		"\xf0\x03\x81\x43", #BTN 10 (Toe switch)
		"\xf0\x03\x81\x10", #BTN 11 (Up arrow)
		"\xf0\x03\x81\x02", #BTN 12 ("Function 1", serves as down arrow)
		"\xf0\x03\x81\x00" #BTN 13 ("Function 2", serves as "function" button)
		)

		LEDs = (
		"\xf0\x03\x04\x20", #LED 0 (FS5, "A")
		"\xf0\x03\x04\x30", #LED 1 (FS6, "B")
		"\xf0\x03\x04\x40", #LED 2 (FS7, "C")
		"\xf0\x03\x04\x50", #LED 3 (FS8, "D")
		"\xf0\x03\x04\x00", #LED 4 (Down arrow)
		"\xf0\x03\x04\x12", #LED 5 (FS1, "Stomp")
		"\xf0\x03\x04\x41", #LED 6 (FS2, "Mod")
		"\xf0\x03\x04\x51", #LED 7 (FS3, "Delay")
		"\xf0\x03\x04\x21", #LED 8 (FS4, "Reverb")
		"\xf0\x03\x04\x61", #LED 9 ("Tap tempo")
		"\xf0\x03\x04\x13", #LED 10 (Wah)
		"\xf0\x03\x04\x03", #LED 11 (Volume)
		"\xf0\x03\x04\x01" #LED 12 ("Function 2", serves as "function" button)
		#"\xf0\x03\x04\x10", #LED 13 (Up arrow), not used
		#"\xf0\x03\x04\x02", #LED 14 ("Function 1"), not used
		)

		#LED state suffixes
		LED_on = "\x01" #On for MKII
		LED_off = "\x00" #Off for MKII
		LED_dim = LED_off #Dim is the same as off for MKII
		


#This function reads in configuration and page names TSV text files
def Read_config_files(Config_file):

	global Page_name4char
	global Page_name16char
	global Effect_name 
	global Message_type
	global Channel_number
	global CC_number
	global Value_off
	global Value_on
	global Effect_state
	global Effect_type
	global Linked_on
	global Linked_off
	global Effect_color
	global Exp_1_channel
	global Exp_1_CC
	global Exp_2_channel
	global Exp_2_CC
	global Tap_channel_number
	global Tap_CC_number
	global Tap_CC_value
	global Tuner_MIDI_channel
	global Tuner_MIDI_CC_number
	global Tuner_MIDI_CC_value_off
	global Tuner_MIDI_CC_value_on
	global Wah_number

	Page_name4char = [] #establish list for first 4 chars of page names
	Page_name16char = [] #establish list for last 16 chars of page names
	Effect_name = [] #establish string list for effect/preset name
	Message_type = [] #establish string list for MIDI message types
	Channel_number = [] #establish string list for MIDI channel numbers
	CC_number = [] #establish string list for CC numbers
	Value_off = [] #establish string list for CC values when effect off
	Value_on = [] #establish string list for CC values when effect on
	Effect_state = [] #establish boolean list for effect state
	Effect_type = [] #establish list for effect type (Ie, IA vs Preset)
	Linked_on = [] #establish list for linked on effects
	Linked_off = [] #establish list for linked off effects
	Effect_color = [] #establish list for effect color (only applies to FBV3)
	Exp_1_channel = [] #establish list for MIDI channel of expression1 effect
	Exp_1_CC = [] #establish list for CC of expression1 effect
	Exp_2_channel = [] #establish list for MIDI channel of expression2 effect
	Exp_2_CC = [] #establish list for CC of expression2 effect
	Tap_channel_number = [] #establish list for tap tempo MIDI message channel numbers
	Tap_CC_number = [] #establish list for tap tempo MIDI CC number
	Tap_CC_value = [] #establish list for tap tempo MIDI CC value
	Wah_number = 1 #Sets "Wah" effect linked to toe switch to effect #1 by default


	for line in open(Config_file, "r"):
		li = line.strip()
		if li.startswith("Toe_switch_effect_link"):
			Wah_number = int(line.split("\t")[1]) #Gets linked wah effect to be turned on/off with toe switch
		elif li.startswith("Tap_tempo_MIDI_command"):
			Tap_channel_number.append(line.split("\t")[1])
			Tap_CC_number.append(line.split("\t")[2])
			Tap_CC_value.append(line.split("\t")[3])
		elif li.startswith("Tuner_MIDI_commands"):
			Tuner_MIDI_channel = int(line.split("\t")[1])
			Tuner_MIDI_CC_number = int(line.split("\t")[2])
			Tuner_MIDI_CC_value_off = int(line.split("\t")[3])
			Tuner_MIDI_CC_value_on = int(line.split("\t")[4])
		elif li.startswith("Page_name"):
			Page_name4char.append((line.split("\t")[1])[1:-1]) #removes quotes
			Page_name16char.append((line.split("\t")[2])[1:-1]) #As this is not at the end of the line, do not need to remove the newline character, otherwise [1:-2]
		elif not li.startswith("#"): #ignore headers
			Effect_name.append((line.split("\t")[1])[1:-1]) #get effect name from 1st column and remove 1st and last chars (quotes)
			Message_type.append(line.split("\t")[2])
			Channel_number.append(line.split("\t")[3])
			CC_number.append(line.split("\t")[4])
			Value_off.append(line.split("\t")[5])
			Value_on.append(line.split("\t")[6])
			temp = line.split("\t")[7] # take 7th column
			if temp.startswith("On"):
				Effect_state.append(True)
			else:
				Effect_state.append(False) #if not "On", just assign false
			Effect_type.append(line.split("\t")[8])
			Linked_on.append(line.split("\t")[9])
			Linked_off.append(line.split("\t")[10])
			Effect_color.append(line.split("\t")[11])
			temp = line.split("\t")[12]
			if not temp.startswith("NA"): #If there is some expression1 MIDI channel set
				Exp_1_channel.append(line.split("\t")[12]) #Take channel
				Exp_1_CC.append(line.split("\t")[13]) #Also take CC number
			else:
				Exp_1_channel.append(16) #Arbitrary, no such channel, 0-15 only
				Exp_1_CC.append(0) #arbitrary
			temp = line.split("\t")[14]
			if not temp.startswith("NA"): #If there is some expression2 MIDI channel set
				Exp_2_channel.append(line.split("\t")[14]) #Take channel
				Exp_2_CC.append(line.split("\t")[15]) #Also take CC number
			else:
				Exp_2_channel.append(16) #Arbitrary, no such channel, 0-15 only
				Exp_2_CC.append(0) #arbitrary

	#Most variables need to be converted to INT to work with MIDO messages
	Channel_number = map(int, Channel_number)
	CC_number = map(int, CC_number)
	Value_off = map(int, Value_off)
	Value_on = map(int, Value_on)
	Effect_color = str(bytearray(map(int, Effect_color))) #converts to int, then bytes, then string
	Exp_1_channel = map(int, Exp_1_channel)
	Exp_1_CC = map(int, Exp_1_CC)
	Exp_2_channel = map(int, Exp_2_channel)
	Exp_2_CC = map(int, Exp_2_CC)
	Tap_channel_number = map(int, Tap_channel_number)
	Tap_CC_number = map(int, Tap_CC_number)
	Tap_CC_value = map(int, Tap_CC_value)
	
def Arduino_read(run_event): #Reads in tagged bytes from arduino, strips tags and places in appropriate queues.
	Arduino_packet = ""
	while run_event.is_set():
		Arduino_byte1 = Arduino.read() #get first byte
		if Arduino_byte1 == "\xf1": #if this is from UART-1 (FBV)
			Arduino_byte2 = Arduino.read() #The next byte after declares how many remaining bytes there are
			Arduino_packet_length = Arduino_byte2.encode("hex") #part of conversion to int
			Arduino_packet_length = int(Arduino_packet_length, 16) #converts to int
			Arduino_packet = Arduino.read(Arduino_packet_length) #get that more many bytes
			if FBV_pass_through == True:
				Arduino_writequeue.put("\xf3" + Arduino_byte2 + Arduino_packet) #Just pass data to HD or other Line 6 unit
			else:
				FBV_readqueue.put(Arduino_packet) #Otherwise place in queue
			if Debug_mode == True:
				elapsed_time = time.time() - start_time #Debugging
				Debug_string = "time {} FBV sent {}".format(elapsed_time, Arduino_packet.encode("hex")) 
				Debug_queue.put(Debug_string) #Debugging
		if Arduino_byte1 == "\xf2": #if this is from UART-2 (MIDI)
			Arduino_byte2 = Arduino.read() #The next byte after declares how many remaining bytes there are
			Arduino_packet_length = Arduino_byte2.encode("hex") #part of conversion to int
			Arduino_packet_length = int(Arduino_packet_length, 16) #convert to int
			Arduino_packet = Arduino.read(Arduino_packet_length) #get that more many bytes
			MIDI_readqueue.put(Arduino_packet) #place in queue
			if MIDI_thru == True:
				Arduino_writequeue.put("\xf2" + Arduino_byte2 + Arduino_packet) #Directs whatever came in to go back out
			if Debug_mode == True:
				elapsed_time = time.time() - start_time
				Debug_string = "time {} MIDI sent {}".format(elapsed_time, Arduino_packet.encode("hex"))
				Debug_queue.put(Debug_string) #Debugging
		if Arduino_byte1 == "\xf3": #if this is from UART-3 (HD)
			Arduino_byte2 = Arduino.read() #The next byte after declares how many remaining bytes there are
			Arduino_packet_length = Arduino_byte2.encode("hex") #part of conversion to int
			Arduino_packet_length = int(Arduino_packet_length, 16) #convert to int
			Arduino_packet = Arduino.read(Arduino_packet_length) #get that more many bytes
			if FBV_pass_through == True:
				Arduino_writequeue.put("\xf1" + Arduino_byte2 + Arduino_packet) #Just pass data from HD or other Line 6 unit to FBV
			else:
				HD_readqueue.put(Arduino_packet) #Otherwise place in queue
			if Debug_mode == True:
				elapsed_time = time.time() - start_time
				Debug_string = "time {} HD sent {}".format(elapsed_time, Arduino_packet.encode("hex"))
				Debug_queue.put(Debug_string) #Debugging

def Arduino_write(run_event):
	while run_event.is_set():
		Arduino_writepacket = Arduino_writequeue.get()
		Arduino.write(Arduino_writepacket)
		if Debug_mode == True:
			elapsed_time = time.time() - start_time
			Debug_string = "time {} Arduino is sending {}".format(elapsed_time, Arduino_writepacket.encode("hex"))
			Debug_queue.put(Debug_string) #Debugging

def Debug_read(run_event):
	while run_event.is_set():
		Debug_string = Debug_queue.get()
		print Debug_string #For debugging purposes

def MIDI_packet_process(run_event):
	while run_event.is_set():
		MIDIread = mido.parse(MIDI_readqueue.get())
		if MIDIread.type == "control_change": #Only responds to CC messages for now
			Type = MIDIread.type
			Channel = MIDIread.channel
			Control = MIDIread.control
			CC_value = MIDIread.value
			for i in range(len(Message_type)): #Could be any variable from this array really
				if (Message_type[i] == Type) and (Channel_number[i] == Channel) and (CC_number[i] == Control) and (Value_on[i] == CC_value) and (Effect_state[i] == False):
					#If this effect is off and being turned on through MIDI
					Toggle_effect(i)
				elif (Message_type[i] == Type) and (Channel_number[i] == Channel) and (CC_number[i] == Control) and (Value_off[i] == CC_value) and (Effect_state[i] == True):
					#If this effect is on and being turned off through MIDI
					Toggle_effect(i)

def HD_packet_process(run_event):
	while run_event.is_set():
		HDread = HD_readqueue.get()
		if HDread == "\xf0\x02\x01\x00":
			Arduino_writequeue.put("\xf3\x09\xf0\x07\x80\x00\x02\x00\x01\x01\x00") #spooking FBV response to HD per protocol
		if Tuner_mode == True:
			if HDread.startswith("\xf0\x05\x08"): #allow pass-through of 1st 4 character display info
				Arduino_writequeue.put("\xf1\x07" + HDread)	
			if HDread.startswith("\xf0\x13"): #allow pass-through of the last 16 character display info
				Arduino_writequeue.put("\xf1\x15" + HDread)

def FBV_packet_process(run_event):
	global Current_page #Need this to modify global variables
	global Exp_vals
	global Exp_1_state
	global Exp_2_state
	Handshake_sent = False
	while run_event.is_set():
		FBVread = FBV_readqueue.get()

		#FBV3 handshake, spooks unit into thinking its connected to Line-6 device (Unclear if required):
		if FBVread == "\xf0\x02\x90\x01":
			Arduino_writequeue.put("\xf1\x04\xf0\x02\x01\x00")
		if (FBVread == "\xf0\x02\x90\x00"): #and (Handshake_sent == False): 
			Arduino_writequeue.put("\xf1\x04\xf0\x02\x50\x00")
			Arduino_writequeue.put("\xf1\x03\xf0\x01\x40")
			Arduino_writequeue.put("\xf1\x05\xf0\x03\x31\x01\x16")
			Handshake_sent = True
		if (FBVread == "\xf0\x02\x90\x00") and (Handshake_sent == True):
			Arduino_writequeue.put("\xf1\x04\xf0\x02\x01\x00")

		if FBVread == Buttons[9] + "\x01": #If Tap-tempo button pressed
			Tap_tempo(1) #Execute tap tempo function with button press

		if FBVread == Buttons[9] + "\x00": #If Tap-tempo button button release
			Tap_tempo(0) #Execute tap tempo function with button release

		if FBVread == Buttons[11] + "\x01": # Page up button pressed
			if Current_page == 7:
				Current_page = 0 #resets back to 0
			else: 
				Current_page += 1 # increment current page
			Update_display(Page_name4char[Current_page], Page_name16char[Current_page])
			Update_colors() 
			Update_LEDs()		

		if FBVread == Buttons[12] + "\x01": #Page down pressed
			if Current_page == 0:
				Current_page = 7 # resets to 7
			else:
				Current_page -= 1 #decrement current page
			Update_display(Page_name4char[Current_page], Page_name16char[Current_page])
			Update_colors()
			Update_LEDs()

		if FBVread == Buttons[10] + "\x01": #Toe switch pressed 
			Effect_state[Wah_number] = not Effect_state[Wah_number] #toggle Wah
			if Effect_state[Wah_number]: #If Wah is now activated
				MIDI_message = mido.Message(type = Message_type[Wah_number], channel = Channel_number[Wah_number], control = CC_number[Wah_number], value = Value_on[Wah_number]) #construct midi message
				Execute_preset(Wah_number) #turn off any other M13 effects on that column
				StringA = "  ON"
				if Wah_number not in Exp_1_users:
					Exp_1_users.append(Wah_number)
			else: #assume wah is off
				MIDI_message = mido.Message(type = Message_type[Wah_number], channel = Channel_number[Wah_number], control = CC_number[Wah_number], value = Value_off[Wah_number]) #construct midi message
				StringA = " OFF"
				if Wah_number in Exp_1_users:
					Exp_1_users.remove(Wah_number)
			Arduino_writequeue.put("\xf2\x03" + str(MIDI_message.bin())) 
			StringB = Effect_name[Wah_number]
			Update_LEDs()
			Update_display(StringA, StringB)

		if FBVread.startswith(Buttons[0:9]) and FBVread[-1:] == "\x01": #If buttons 0-8 were pressed, need to reference 0:9
			Button_number = FBVread[:-1] #take everything but last hex value (byte)
			Button_number = Buttons.index(Button_number) #get index from array
			Button_number = Button_number + (Current_page * 9) #shifts button number based on page
			Toggle_effect(Button_number)

		if FBVread.startswith("\xf0\x03\x82\x00") and len(Exp_1_users) !=0: # if Exp1 values are issued and effect(s) are using it
			Exp_vals[0] = struct.unpack("B", FBVread[-1:])[0] # extracts the last hex value, converts to int and saves
			Exp_function(1) #issue corresponding MIDI for users of Exp1		
	
		if FBVread.startswith("\xf0\x03\x82\x01") and len(Exp_2_users) !=0: # if Exp2 values are issued and effect(s) are using it
			Exp_vals[1] = struct.unpack("B", FBVread[-1:])[0] # extracts the last hex value, converts to int and saves
			Exp_function(2) #issue corresponding MIDI for users of Exp2

def Toggle_effect(Button_number):
	Effect_state[Button_number] = not Effect_state[Button_number] #toggle effect state
	if Effect_state[Button_number]: #If effect state now on, note this is only set up for CC toggle messages now
		StringA = "  0N"
		MIDI_message = mido.Message(type = Message_type[Button_number], channel = Channel_number[Button_number], control = CC_number[Button_number], value = Value_on[Button_number]) #construct midi message
	else: #Assumes effect is off
		MIDI_message = mido.Message(type = Message_type[Button_number], channel = Channel_number[Button_number], control = CC_number[Button_number], value = Value_off[Button_number]) #construct midi message
		StringA = " 0FF"
	StringB = Effect_name[Button_number]
	Arduino_writequeue.put("\xf2\x03" + str(MIDI_message.bin())) #convert to bytes and put in queue

	if (Effect_state[Button_number] == True) and (Effect_type[Button_number] == "Preset"):
		Execute_preset(Button_number) #execute preset(s) for that line

	if (Effect_state[Button_number] == True) and (Exp_1_channel[Button_number] != 16): #if on and associated with exp1
		Exp_1_users.append(Button_number)
	if (Effect_state[Button_number] == True) and (Exp_2_channel[Button_number] != 16): #if on and associated with exp2
		Exp_2_users.append(Button_number)
	if (Effect_state[Button_number] == False) and (Exp_1_channel[Button_number] != 16): #if off and associated with exp1
		Exp_1_users.remove(Button_number)
	if (Effect_state[Button_number] == False) and (Exp_2_channel[Button_number] != 16): #if off and associated with exp2
		Exp_2_users.remove(Button_number)

	Update_LEDs() #Update LEDs 0-9
	Update_display(StringA, StringB) #Update display with effect status

def Exp_function(Pedal_number):
	if Pedal_number == 1:
		for i in Exp_1_users:
			MIDI_message = mido.Message(type = "control_change", channel = Exp_1_channel[i], control = Exp_1_CC[i], value = Exp_vals[0])
			Arduino_writequeue.put("\xf2\x03" + str(MIDI_message.bin()))
	if Pedal_number == 2:
		for i in Exp_2_users:
			MIDI_message = mido.Message(type = "control_change", channel = Exp_2_channel[i], control = Exp_2_CC[i], value = Exp_vals[1])
			Arduino_writequeue.put("\xf2\x03" + str(MIDI_message.bin()))

def Execute_preset(Button_number):
	Effects_on = (Linked_on[Button_number]).split(",") #get list of Linked_on effects
	Effects_off = (Linked_off[Button_number]).split(",") #get list of Linked_off effects
	if Effects_on[0].isdigit(): #Make sure it isn't NA
		Effects_on = map(int, Effects_on) #Convert to ints
		for i in Effects_on:
			if not Effect_state[i]: #If effect is off
				Effect_state[i] = True #turn it on	
				MIDI_message = mido.Message(type = Message_type[i], channel = Channel_number[i], control = CC_number[i], value = Value_on[i]) #construct midi message
				Arduino_writequeue.put("\xf2\x03" + str(MIDI_message.bin())) #convert to bytes and put in queue
			if Exp_1_channel[i] != 16 and i not in Exp_1_users: #also add any expression effects
				Exp_1_users.append(i)
			if Exp_2_channel[i] != 16 and i not in Exp_2_users:
				Exp_2_users.append(i)

	if Effects_off[0].isdigit(): #Make sure it isn't NA
		Effects_off = map(int, Effects_off) #Convert to ints
		for i in Effects_off:
			if Effect_state[i]: #If effect is on
				Effect_state[i] = False #turn it off	
				MIDI_message = mido.Message(type = Message_type[i], channel = Channel_number[i], control = CC_number[i], value = Value_off[i]) #construct midi message
				Arduino_writequeue.put("\xf2\x03" + str(MIDI_message.bin())) #convert to bytes and put in queue
			if Exp_1_channel[i] != 16 and i in Exp_1_users: #also remove expression effects
				Exp_1_users.remove(i)
			if Exp_2_channel[i] != 16 and i in Exp_2_users:
				Exp_2_users.remove(i)
	Update_LEDs() #Update LEDs again in case it changes anything


def Tap_tempo(Button_status):
	global Tap_last_pressed
	global Tap_index
	global Tap_intervals
	global Tap_time
	global Tap_held
	global Tuner_mode	
	if Button_status == 1: #If button pressed in:
		if Tuner_mode == True: #if Tuner mode is enabled, turn it off
			Tuner_mode = False
			MIDI_message = mido.Message(type = "control_change", channel = Tuner_MIDI_channel, control = Tuner_MIDI_CC_number, value = Tuner_MIDI_CC_value_off)
			Arduino_writequeue.put("\xf2\x03" + str(MIDI_message.bin()))
			Update_display(Page_name4char[Current_page], Page_name16char[Current_page])
		else:
			Arduino_writequeue.put("\xf1\x05\xf0\x03\x04\x61" + LED_on) #Light up the button
			Tap_held = True 
			Tap_intervals[Tap_index] = time.time() - Tap_last_pressed
			Tap_last_pressed = time.time() #Reset timer
			if Tap_index == 2:
				Tap_index = 0 #Reset to zero
			else:
				Tap_index = Tap_index + 1 #increment
			Temp_tap_time = sum(Tap_intervals) / 3 #Get average time of taps
			if Temp_tap_time < 3.0: #Only if it's within a reasonable range (< 3s), will it get assigned to global variable
				Tap_time = Temp_tap_time
			#Now send MIDI messages
			for i in range(0, len(Tap_channel_number)):
				MIDI_message = mido.Message(type = "control_change", channel = Tap_channel_number[i], control = Tap_CC_number[i], value = Tap_CC_value[i]) #construct MIDI message
				Arduino_writequeue.put("\xf2\x03" + str(MIDI_message.bin())) #convert to bytes and put in queue
	if Button_status == 0: 
		Arduino_writequeue.put("\xf1\x05\xf0\x03\x04\x61" + LED_off)
		Tap_held = False


def Timers(run_event):
	global Tuner_mode
	global Tap_held
	global Tap_last_pressed
	Tap_held_time = 0
	time.sleep(10) #Don't start sending tap tempo until after 10 seconds after init (otherwise runs the risk of getting sent before init signals)
	while run_event.is_set():
		Local_tap_time = Tap_time - 0.1 #Get updated tap time from global variable, subtract time needed to blink LED
		Arduino_writequeue.put("\xf1\x05\xf0\x03\x04\x61" + LED_on)
		time.sleep(0.1) #keep light on for 100ms
		Arduino_writequeue.put("\xf1\x05\xf0\x03\x04\x61" + LED_off)
		time.sleep(Local_tap_time)
		if (Tap_held == True):
			Tap_held_time = time.time()
		if (Tap_held == True) and (Tap_held_time - Tap_last_pressed > 4.0): #if Tap tempo is held for more than 4 seconds
			MIDI_message = mido.Message(type = "control_change", channel = Tuner_MIDI_channel, control = Tuner_MIDI_CC_number, value = Tuner_MIDI_CC_value_on)
			Arduino_writequeue.put("\xf2\x03" + str(MIDI_message.bin())) #put in queue
			Tuner_mode = True #Turn Tuner mode on

def Update_display(stringA, stringB):
	stringA = "\xf0\x05\x08" + stringA.encode("ascii") #convert to bytes and adds sysex header for first-4 characters in LCD display
	stringB = "\xf0\x13\x10\x00\x10" + stringB.encode("ascii") #convert to bytes and add sysex header for last-16 characters in LCD display
	Arduino_writequeue.put("\xf1\x07" + stringA)
	Arduino_writequeue.put("\xf1\x15" + stringB)



def Update_colors():
	for i in range(len(Colors)):
		StringA = Colors[i] + Effect_color[i + (Current_page * 9)] # appends assign colors
		Arduino_writequeue.put("\xf1\x05" + StringA)


def Update_LEDs():
	#Note, does not make use of page up/down (MKII only) or Function switch at this time
	for i in range (0, 9): #in actuality this gives 0-8
		StringA = LEDs[i]
		if Effect_state[i + (Current_page * 9)] == True: #converts page number
			StringA = StringA + LED_on
		else:
			StringA = StringA + LED_dim
		Arduino_writequeue.put("\xf1\x05" + StringA)
	if len(Exp_1_users) == 0:
		StringA = LEDs[10] + LED_off #Turn off Wah LED
	else:
		StringA = LEDs[10] + LED_on #Turn on Wah LED
	Arduino_writequeue.put("\xf1\x05" + StringA)
	if len(Exp_2_users) == 0:
		StringA = LEDs[11] + LED_off #Turn off Vol LED
	else:
		StringA = LEDs[11] + LED_on #Turn on Vol LED
	Arduino_writequeue.put("\xf1\x05" + StringA)

def main():
	#Default initialization parameters:
	Config_file = "Config.txt"
	Model = "FBV3" #May also be "MkII"
	Serial_port = "/dev/ttyACM0"
	global Debug_mode
	global FBV_pass_through
	global MIDI_thru
	Debug_mode = False
	FBV_pass_through = False
	MIDI_thru = False	

	#Get command line arguments:
	try:
		opts, args = getopt.getopt(sys.argv[1:], "c:d:f:m:s:",["config-file=", "debug_mode=", "FBV_pass_through=", "model=", "serial_port=", "thru="])
	except getopt.GetoptError as err:
		print "Incorrect syntax, correct usage is: "
		print "./FBV_MIDI.py --config-file=Config.txt --debug_mode=off --FBV_pass_through=off --model=FBV3 --serial_port=/dev/ttyAMC0 --thru=off"
		sys.exit(2)
	
	for opt, arg in opts:
		if opt in ("-c", "--config-file"):
			#use alternative config file
			Config_file = arg
		if opt in ("-d", "--debug_mode"):
			Debug_mode = arg
		if opt in ("-f", "--FBV_pass_through"):
			FBV_pass_through = arg
		if opt in ("-m", "--model"):
			Model = arg
		if opt in ("-s", "--serial_port"):
			Serial_port = arg
		if opt in ("-t", "--thru"):
			MIDI_thru = arg

	if Debug_mode == "on":
		Debug_mode = True
	else:
		Debug_mode = False

	if FBV_pass_through == "on":
		FBV_pass_through = True
	else:
		FBV_pass_through = False
	
	if MIDI_thru == "on":
		MIDI_thru = True
	else:
		MIDI_thru = False

	print "Using configuration file: ", Config_file
	print "Model of controller is: Line 6 ", Model
	print "Using Arduino serial at: ", Serial_port
	print "Debug mode on: ", Debug_mode
	print "FBV_Pass_through on: ", FBV_pass_through
	print "MIDI thru mode on: ", MIDI_thru

	Initialize_options(Serial_port, Model) #Initialize global variables
	Read_config_files(Config_file) #Read in files as global lists

	run_event = threading.Event()
	run_event.set()	
	
	threadArduino_read = threading.Thread(target=Arduino_read, args = (run_event,))
	threadArduino_write = threading.Thread(target=Arduino_write, args = (run_event,))
	threadMIDI_packet_process = threading.Thread(target=MIDI_packet_process, args = (run_event,))
	threadHD_packet_process = threading.Thread(target=HD_packet_process, args = (run_event,))
	threadFBV_packet_process = threading.Thread(target=FBV_packet_process, args = (run_event,))
	threadDebug_read = threading.Thread(target=Debug_read, args = (run_event,))
	threadTimers = threading.Thread(target=Timers, args = (run_event,))

	threadArduino_read.daemon = True
	threadArduino_write.daemon = True
	threadMIDI_packet_process.daemon = True
	threadHD_packet_process.daemon = True
	threadFBV_packet_process.daemon = True
	threadDebug_read.daemon = True
	threadTimers.daemon = True

	threadArduino_read.start()
	threadArduino_write.start()
	threadMIDI_packet_process.start()
	
	if FBV_pass_through == False:
		threadHD_packet_process.start()
		threadFBV_packet_process.start()
		threadTimers.start()
	
	if Debug_mode == True:
		threadDebug_read.start()


	try:
		while 1:
			time.sleep(10) #Unclear if needed
	except KeyboardInterrupt:
		print "closing threads"
		run_event.clear()
		print "threads successfully closed"

if __name__ == "__main__": #Run the progrom
	main()


