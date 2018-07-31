/*
FBV_MIDI.ino
Version 1.0
7-29-18
kevin.quann@gmail.com
This Arduino Mega sketch takes full-duplex serial data (either MIDI or sysex data from FBV or Pod HD pro) and "tags" it depending which serial it came from.
This then gets sent over the main serial bus (USB) to Rasbperry Pi for processing.
Data that is sent back to the Arduino is similarly tagged to address it to the proper serial port (MIDI, FBV or HD).
*/

unsigned char FBV_bytes[50], MIDI_bytes[50], HD_bytes[50], Output_bytes[50]; //Declares arrays of length 50 if needed to go that long, needs to be unsigned
byte FBV_index = 0, MIDI_index = 0, HD_index = 0, Output_index = 0; //indices for where to store characters
byte FBV_length = 0, MIDI_length = 0, HD_length = 0, Output_length = 0; //lengths for messages
unsigned char MIDI_type = 0; //Used to determine type of MIDI signal
byte Output_address = 0; //this will be "tag" as to which UART should be used for output

void setup() 
{
  Serial.begin(115200); //This is baud rate for UART0 (ie USB port to RPi)
  Serial1.begin(31250); //Initialize UART1 (FBV) for MIDI speed
  Serial2.begin(31250); //Initialize UART2 (MIDI) for MIDI speed
  Serial3.begin(31250); //Initialize UART3 (optional POD HD) for MIDI speed
}
  

void readUART1() //This is for FBV
{
  while (Serial1.available() > 0)
  {
    if (FBV_index == 0) //if this is the first byte in the stream
    {
      FBV_bytes[0] = 241; //prepend "tag" of "F1" to string to tell which UART received data
      FBV_bytes[1] = 1; //Initialize length of 1, to be modified later
      FBV_bytes[2] = Serial1.read(); //read 1st byte into 3rd position of array
      if (FBV_bytes[2] == 240)
      {
        FBV_index++; //sanity check, increment only if "F0" is the first received byte
      }
    }
    else if (FBV_index == 1) //if this is second byte
    {
      FBV_bytes[3] = Serial1.read(); //read in 2nd byte
      FBV_length = FBV_bytes[3]; //This is length bit from sysex message (total -4)
      FBV_bytes[1] = (FBV_length + 2); //This corrects to the "total" message length -2 (not including prepended address and size bytes)
      FBV_index++; //increment
    }
    else if ((FBV_index > 1) && (FBV_index < FBV_length + 2))
    {
      FBV_bytes[(FBV_index + 2)] = Serial1.read(); // keep adding bytes
      FBV_index++; //increment
    }
    if (FBV_index == (FBV_length + 2))
    {
      FBV_bytes[(FBV_index + 2)] = '\0'; //Null terminate string, not sure if necessary.
      Serial.write(FBV_bytes, (FBV_length + 4)); //Dump tagged message to UART0 (USB)
      FBV_index = 0; //reset
    }
  }
}
  
void readUART2() //This is for MIDI
{
  while (Serial2.available() > 0)
  {
    if (MIDI_index == 0) //if this is the first byte in the stream
    {
      MIDI_bytes[0] = 242; //prepend "tag" of "F2" to string to tell which UART received
      MIDI_bytes[1] = 1; //Initialize length at 1, to be modified later
      MIDI_bytes[2] = Serial2.read(); //read 1st byte into the 3rd position of array
      MIDI_type = MIDI_bytes[2] >> 4; //Shift down the first 4 bits to get the "type" of MIDI signal (ie CC, PC, note-on, etc)
      if ((MIDI_type == 12) || (MIDI_type == 13)) // if 1100 (PC) or 1101 (CP)
       {
         MIDI_length = 2; //These are 2 byte signals
         MIDI_bytes[1] = 2; //declare explicitly how long subsequent string will be (used for python)
         MIDI_index++; //increment counter
       }
       else if ((MIDI_type == 8) || (MIDI_type == 9) || (MIDI_type == 10) || (MIDI_type == 11) || (MIDI_type == 14))
       {
         MIDI_length = 3; //Most other signals are 3 bytes
         MIDI_bytes[1] = 3; //declare how long subsequent string will be
         MIDI_index++; //increment counter
       }
       /*else if (MIDI_type == 15) //If this is a sysex message, suppress functionality for now (will need future implementation)
       {
         MIDI_length = 3; //Set arbitrarily to 3 for now
       }*/
       else
       {
         MIDI_index = 0; //If not a MIDI signal, just reset. Not needed probably.
       }
    }
    else if ((MIDI_index != 0) && (MIDI_index < MIDI_length))
    {
      MIDI_bytes[MIDI_index + 2] = Serial2.read(); //read the next byte into array, offset by 2 for preceeding UART tag + length byte.
      MIDI_index++; //increment counter
    }
    if (MIDI_index == MIDI_length) //Once array fills up
    {
      MIDI_bytes[MIDI_index + 2] = '\0'; //null terminate the position 1-past the actual data bytes (keep in mind starts at 0)
      Serial.write(MIDI_bytes, (MIDI_length + 2)); //flush to UART0 (USB)
      MIDI_index = 0; //Reset counter
    }
  }
}

void readUART3() //This is for HD
{
  while (Serial3.available() > 0)
  {
    if (HD_index == 0) //if this is the first byte in the stream
    {
      HD_bytes[0] = 243; //prepend "tag" of "F3" to string to tell which UART received data
      HD_bytes[1] = 1; //Initialize length of 1, to be modified later
      HD_bytes[2] = Serial3.read(); //read 1st byte into 3rd position of array, should be F0
      if (HD_bytes[2] == 240)
      {
        HD_index++; //sanity check, increment only if "F0" is the first received byte
      }
    }
    else if (HD_index == 1) //if this is second byte
    {
      HD_bytes[3] = Serial3.read(); //read in 2nd byte
      HD_length = HD_bytes[3]; //This is the length bit from sysex message
      HD_bytes[1] = (HD_length + 2); //This corrects to the "total" message length -2 (not including prepended address and size bytes)
      HD_index++; //increment
    }
    else if ((HD_index > 1) && (HD_index < HD_length + 2))
    {
      HD_bytes[(HD_index + 2)] = Serial3.read(); // keep adding bytes
      HD_index++; //increment
    }
    if (HD_index == (HD_length + 2))
    {
      HD_bytes[(HD_index + 2)] = '\0'; //Null terminate string, not sure if necessary.
      Serial.write(HD_bytes, (HD_length + 4)); //Dump tagged message to UART0 (USB)
      HD_index = 0; //reset
    }
  }
}


void writeUARTs()
{
  while (Serial.available() > 0) //if signal is being sent to Arduino
  {
    if (Output_index == 0) // if this is first byte in stream
    {
      Output_address = Serial.read(); //get UART address tag
      Output_index++; //increment index
    }
    else if (Output_index == 1) //if it's the second byte
    {
      Output_length = Serial.read(); //get "length" of following message
      Output_index++; //increment index
    }
    else if ((Output_index > 1) && (Output_index < (Output_length + 2))) //after 1st two bytes, read the actual signal (offset by 2)
    {
      Output_bytes[(Output_index - 2)] = Serial.read(); //read in bytes
      Output_index++; //increment index
    }
        
    if (Output_index == (Output_length + 2)) //once it's full
    {
      Output_bytes[Output_index - 2] = '\0'; //Null terminate next byte (not sure it's needed)
      if (Output_address == 241) //if this is designated F1, send to UART1 (FBV)
      {
        Serial1.write(Output_bytes, Output_length); //flush string
      }
      else if (Output_address == 242) //if this is designated F2, send to UART2 (MIDI)
      {
        Serial2.write(Output_bytes, Output_length);
      }
      else if (Output_address == 243) //if this is designated F3, send to UART3 (HD)
      {
        Serial3.write(Output_bytes, Output_length);
      }
      Output_index = 0; //reset index
    }
  }
}
 
  void loop() 
{
 // run over and over
  readUART1();
  readUART2();
  readUART3();
  writeUARTs();
 
}
