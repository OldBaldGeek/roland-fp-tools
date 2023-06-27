#!/usr/bin/python
#
# spelunky.py: Spelunking the Roland FP-90/60
#
# Python 2.7
#
# Updated 21 June 2020
#
# CAUTION: this program can generate MIDI messages that are not documented by
# Roland or other equipment manufacturers.  It is possible that some such
# messages may have a negative impact on the operation of a device, perhaps
# causing lockup or the loss of configuration data. In the worst case, it is
# possible that there may be a message that permanently damage some device.
# It is the responsibility of the user to evaluate the potential risk before
# using this program.
#
# Copyright (c) 2020 by John Hartman
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#   SOFTWARE.
#
import sys
import string
import time
from time import sleep
import csv
import os
import select
import readline
import threading

# Device to be used
MIDI_DEVICE = '/dev/midi1'

# Default MIDI output channel
MIDI_CHANNEL = 4
g_channel = MIDI_CHANNEL

# Global MIDI dumper, initialized in main
g_midiDumper = None

# "Super category" including all tones
SUPER_CAT = 'All'


# Tests of SysEx reads from FP-90 show
# - FP-90 may return fewer bytes than reqested, e.g., 01 00 00 00 returns at
#   most 12 bytes regardless of the larger number asked.
#
# - 01 00 00 00 has 12 bytes
# - 01 01 00 00 has 3 bytes
# - 01 02 00 00 has 3 bytes
# - 02 00 00 00 has 13 bytes
# - 02 10 00 00 through 02 10 05 7F
# - 03 00 XX 00 has 13 bytes for XX 00 through 12 (19. records)
# - 03 10 00 00 through 03 10 4B 7F
# - 03 20 00 00 through 03 20 12 7F
# - 03 30 00 00 through 03 30 12 7F
# Nothing readable above 03 30 12 7F
#
# A read with a large length (1024) that INCLUDES multiple regions (as 03 00 00 00)
# gets MULTIPLE responses, one per region.
# That may be used to do a quicker data census, at the expense of fancier
# reply decoding.
# But it may not get ALL possible regions:
# May be due to SysEx SENT by the piano, causing the piano to send SysEx
# when a parameter changes rather than in response to a SysEx read.
# Those messages cover different ranges.
#
# 01 00 00 00 has 12 bytes
#          00  00
#          01  04  Main tuning 1/3.  440.0 is 04 00 00.  415.3 is 00 01 08
#                  MIDI Implementation doc specifies the format for use via RPN
#          02  00  Main tuning 2/3
#          03  00  Main tuning 3/3
#          04  00  Temperament. 0 is Equal
#          05  00  Temperament Key.  0 is C
#          06  01  Hammer. 0 is Off.
#          07  04  
#          08  02  Ambience, 0 to 10. (Adjust with Ambience button +-)
#          09  01
#          0A  40
#          0B  32  Touch, 0 to 100. (Adjust with Function 1)
#
# 01 01 00 00 has 3 bytes
#          00  00  MIDI Bank MS for main tone
#          01  44  MIDI Bank LS
#          02  00  MIDI Program (minus 1)
#
# 01 02 00 00 has 3 bytes
#          00  00
#          01  00
#          02  01  Some tones have 00, some 01; reason unclear
#
# 02 00 00 00 has 13 bytes
#          00  00  Piano number (index into piano data)?  Concert=0, Ballad=1 etc.
#          01  05  Piano Designer: lid
#          02  04  PD: full scale resonanace
#          03  03  PD: damper resonance
#          04  3F  PD: hammer noise.  Signed int, 0x40 is 0
#          05  02  PD: duplex
#          06  03  PD: key off resonance
#          07  04  PD: cabinet resonance
#          08  00  PD: soundboard type
#          09  03  PD: damper noise
#          0A  03  PD: key off noise.
#          0B  01 
#          0C  01 
#
# 02 10 00 00 through 02 10 05 7F
#   These seem to be live Piano designer settings for the current Tone.
#   Changed in bulk when various acoustic pianos are selected.
#
# Run Piano Partner and see (on one run)
# (These may be INITIATED by the piano?)
#   01:00:01:00 17 bytes
#     0000  00 40 40 00 00 00 00 05 00 46 04 04 01 01 01 00 
#     0010  01 
#   01:00:01:01 1 byte
#     01:00:01:01 has 1 bytes
#     0000  3D 
#   01:00:02:00 36 bytes
#     0000  00 36 40 40 40 3B 01 00 00 04 05 00 0B 02 00 09 
#     0010  01 00 00 2D 04 00 40 40 02 00 02 00 40 32 00 04 
#     0020  00 05 00 01 
#   01:00:02:13 1 byte
#     0000  2D
#
# Another run gets
#   01:00:07:00 has 8 bytes
#     0000  00 00 00 03 0E 0C 01 0A 
#   01:00:08:00 has 1 bytes
#     0000  01 
#   message has 15 bytes
#     0000  F0 7E 10 06 02 41 19 03 00 00 0B 01 00 00 F7 
#              universal
#                 device ID (Roland)
#                    sub-id1: general info
#                       sub-id2: identify reply
#                          41: ID Roland
#                             19 03: Device family
#                                    00 00: Device family number
#                                          0B 01 00 00: software revision
#
# BUT: Piano Partner then says "cannot connect"
# Cycling piano power doesn't help
# Eventually comes back.
# Try to read these addresses and get nothing back.
# Maybe they are writes FROM the iPad to unlock or request something.
# Eventually return to factory defaults.  Need to re-pair Bluetooth.
# Piano Partner and Designer work.
#
# During a run with PianoPartner, tone changes from the piano sent both MIDI
# CC/PC AND SysEx:
# 01:02:00:02 1 byte
# 01:01:00:00 3 bytes: the tone info as per MIDI
# 01:00:02:07 3 bytes:
# 01:00:02:00 1 byte: sent with split button (0=single, 1=split, 2=dual)
# 01:00:02:0A 3 bytes: sent with split, but NOT the MIDI value of the left tone
#    0A MAY be the button number (5=button 6/other)
#    0C MAY be the voice number on that button
# 01:00:02:0D 3 bytes: sent with dual, but NOT the MIDI value of tone2
#    0D the button number (4=button 5/pad)
#    0E,0F voice number (0-127 in each byte) on that button
# After a power cycle, these no longer occur; only MIDI CC/PC
# Presumably some command from the iPad turned on "report changes" mode?
#
# The 01:00:xx:00 don't respond to reads.  Perhaps ONLY notifications?
#
# CC12 setting received via MIDI STAYS WITH a Tone (EP2 etc)
# Note that this means a Registration will thus affect its Tones.
# To return to the stock version, need to restore EACH TONE.
#
# Not quite that simple: turning rotary on for ONE tonewheel organ turns it
# on for all of them, doesn't affect CC12 on OTHER types.
#
# With MidiWrench on the iPad via BlueTooth and this program on USB:
# - key and control data from the piano are seen by both
# - this program and MidiWrench do NOT see output from each other
# - having USB plugged into Linux, even with this program not running,
#   may mess up the Roland iPad programs.  This MAY BE because the programs
#   seem to rely on the piano sending SysEx to report changes.  Perhaps these
#   are NOT sent to both BlueTooth and USB?  See them on USB.
#

#=============================================================================
# Convert a_string to int and return it.
# If a_string is not an integer, return a_errorValue
def AsInt( a_string, a_errorValue ):
  try:
     return int(a_string)
  except ValueError:
     return a_errorValue

#=============================================================================
# Dump a set of bytes in hex from a_first to a_last-1
def DumpHex( a_title, a_bytes, a_first, a_last ):
   print( '%s has %d bytes (%d to %d of %d)' %
          (a_title, a_last - a_first, a_first, a_last-1, len(a_bytes)) )
   stg  = ''
   for jx in range( 0, a_last - a_first ):
      if (jx % 16) == 0:
         if jx > 0:
            stg += '\n'
         stg += ('  %04X  ' % jx)
      stg += ( '%02X ' % a_bytes[a_first + jx] )

   print( stg )

#=============================================================================
# Send a MIDI message
def SendMidi( a_dev, a_bytes ):
   bytes = bytearray()
   for b in a_bytes:
      if b > 0xFF:
         print( 'Purported MIDI string has a value larger than 0xFF' )
         return
      bytes.append(b)
   os.write( a_dev, bytes )

#=============================================================================
# Information about a Tone
class Tone:
   def __init__( self, a_index, a_location, a_name, a_msb, a_lsb, a_pc, a_category ):
      self.index = a_index              # position in tones list
      self.location = a_location        # location on FP-90
      self.name = a_name                # name on FP-90
      self.msb = a_msb                  # Bank select hi, lo, and program
      self.lsb = a_lsb
      self.pc = a_pc
      self.category = a_category        # sound category from my spreadsheet

#=============================================================================
class ToneList:
   def __init__( self ):
      self.dev = -1                     # Device handle to MIDI device
      self.currentCategory = ''         # Select category
      self.currentTone = 0              # Selected tone index
      self.tones = []                   # List tones, since their names may not be unique
      self.categories = {}              # Dictionary of category names
      self.toneByLoc = {}               # Dictionary of tone indexes by location
      self.toneByName = {}              # Dictionary of tone indexes by name
      self.toneVars = {}                # Dictionary of tone variables

   #=============================================================================
   # Read the tone list CSV file
   #"Location","Name","MSB","LSB","PC","Category"
   def ProcessToneList( self, a_fileName ):
      print( 'Processing tone list "%s"' % a_fileName )

      self.categories[SUPER_CAT] = SUPER_CAT
      rowNumber = 1
      index = 0
      with open( a_fileName, 'rb' ) as csvFile:
         reader = csv.reader( csvFile, dialect='excel' )
         for row in reader:
            if (rowNumber == 1):
               rowNumber += 1
            else:
               location = row[0]
               name = row[1]
               category = row[5]
               if len(category) == 0:
                  category = '?'

               self.tones.append( Tone( index, location, name, 
                                        int(row[2]), int(row[3]), int(row[4]),
                                        category ) )

               self.categories[category] = category
               self.toneByLoc[location]  = index
               self.toneByName[name]     = index
               if len(self.currentCategory) == 0:
                  self.currentCategory = category
                  self.currentTone = index
               index += 1

   #=============================================================================
   # Show Categories
   def ShowCategories( self ):
      # Dump the categories in alphabetical order
      print( 'Categories' )
      for category, catData in sorted( self.categories.iteritems() ):
         print( '  "%s"' % catData )

   #=============================================================================
   # Show Tones of a specified category ordered by location
   def ShowTones( self, a_category ):
      # Dump the tones in order by location (matching the spreadsheet)
      if len(a_category) == 0:
         a_category = self.currentCategory
      if a_category in self.categories:
         self.currentCategory = a_category
      else:
         print( 'Unknown category "%s"' % a_category )
         return

      print( 'Category "%s"' % a_category )
      if a_category != SUPER_CAT:
         print( ' Tone Name..............   Location....   MSB LSB  PC' )
         for toneData in self.tones:
            if (a_category == '') or (toneData.category == a_category):
               print( '  %3d) %-20s %-12s   %3d %3d %3d' %
                      (toneData.index, toneData.name, toneData.location,
                       toneData.msb, toneData.lsb, toneData.pc) )

   #=============================================================================
   # Show Tones of a specified category ordered by name
   def ShowTonesByName( self, a_category ):
      # Now dump the category in alphabetical order by name
      if len(a_category) == 0:
         a_category = self.currentCategory

      if a_category != SUPER_CAT:
         print( 'By name' )
         print( ' Tone Name..............   Location....   MSB LSB  PC' )
         for name, index in sorted( self.toneByName.iteritems() ):
            toneData = self.tones[ index ]
            if (a_category == '') or (toneData.category == a_category):
               print( ' %3d) %-20s %-12s   %3d %3d %3d' %
                      (toneData.index, toneData.name, toneData.location,
                       toneData.msb, toneData.lsb, toneData.pc) )

   #=============================================================================
   # Show the current tone
   def ShowCurrentTone( self ):
      toneData = self.tones[self.currentTone]
      print( 'Tone:%d name:"%s"  location:"%s"  Bank:%s/%s Program:%s in category "%s"' %
             (toneData.index, toneData.name, toneData.location,
              toneData.msb, toneData.lsb, toneData.pc,
              toneData.category ) )

   #=============================================================================
   # Select a tone by number
   # Return True if tone selected, else False
   def SelectTone( self, a_toneIndex ):
      if (a_toneIndex >= 0) and (a_toneIndex < len(self.tones)):
         toneData = self.tones[ a_toneIndex ]
         # SUPER_CAT is a "super category" that overrides and real categories
         if self.currentCategory != SUPER_CAT:
            self.currentCategory = toneData.category
         self.currentTone = toneData.index
         print( '%3d) %-20s %-12s   Bank %s/%s Program %s in category "%s"' %
                (toneData.index, toneData.name, toneData.location,
                 toneData.msb, toneData.lsb, toneData.pc,
                 toneData.category ) )
         SendMidi( self.dev, [ 0xB0 + g_channel - 1, 0,  toneData.msb ] )
         SendMidi( self.dev, [ 0xB0 + g_channel - 1, 32, toneData.lsb ] )
         SendMidi( self.dev, [ 0xC0 + g_channel - 1, toneData.pc - 1 ] )
         return True
      else:
         print( 'Tone number must be between 0 and %d' % (len(self.tones)-1) )
         return False

   #=============================================================================
   # Select the next tone after or before the current index
   def SelectNextTone( self, a_delta ):
     nextTone = self.currentTone
     while True:
        nextTone += a_delta
        if (nextTone < 0) or (nextTone >= len(self.tones)):
           print( 'No more tones in category %s' % self.currentCategory )
           break

        if ((self.tones[nextTone].category == self.currentCategory) or
            (self.currentCategory == SUPER_CAT)):
           self.SelectTone(nextTone)
           break

   #=============================================================================
   # Tone selection commands
   # - single word interpreted as a tone variable: read previous value
   # - else second word interpreted as a tone number: set variable to value
   def ToneVar( self, a_cmd ):
     var = a_cmd[0]
     if len(a_cmd) > 1:
        tone = a_cmd[1]
        self.toneVars[var] = tone
     elif var in self.toneVars:
        tone = self.toneVars[var]
     else:
        print( 'Variable "%s" has not been set' % var )
        return

     try:
        retval = self.SelectTone( int(tone) )
     except ValueError:
        print( 'Invalid tone value "%s"' % tone )

#=============================================================================
# Return a string for MIDI Controller number
def ControllerName(a_ccNumber):
   retval = '%d' % a_ccNumber
   if a_ccNumber in MidiDumper.ccNames:
      retval += '(%s)' % MidiDumper.ccNames[a_ccNumber]
   return retval

#=============================================================================
# Class to dump a buffer of MIDI messages
class MidiDumper:
   ccNames = { 0:'Bank',
               1:'Modulation',
               2:'Breath',
               4:'Foot',
               5:'Portamento Time',
               6:'Data MSB',
               7:'Volume',
               8:'Balance',
               10:'Pan',
               11:'Expression',
               12:'Effect Ctl1',
               13:'Effect Ctl2',
               32:'Bank LSB',
               33:'Modulation LSB',
               34:'Breath LSB',
               36:'Foot LSB',
               37:'Portamento Time LSB',
               38:'Data LSB',
               39:'Volume LSB',
               40:'Balance LSB',
               42:'Pan LSB',
               43:'Expression LSB',
               44:'Effect Ctl1 LSB',
               45:'Effect Ctl2 LSB',
               64:'Damper',
               65:'Portamento',
               66:'Sustenuto',
               67:'Soft',
               68:'Legato',
               69:'Hold',
               70:'Variation',
               71:'Resonance',
               72:'Release Time',
               73:'Attack Time',
               74:'Brightness',
               75:'Decay Time',
               76:'Vibrato Rate',
               77:'Vibrato Depth',
               78:'Vibrato Delay',
               91:'Reverb Level',
               93:'Chorus Level',
               98:'NRPN-MSB',
               99:'NRPN-LSB',
               100:'RPN-MSB',
               101:'RPN-LSB',
               120:'All Sound Off',
               121:'Reset All',
               122:'Local Control',
               123:'All Notes Off',
               124:'Omni Off',
               125:'Omni On',
               126:'Mono On',
               127:'Mono Off'
             }
      
   noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

   #=============================================================================
   def __init__(self, a_dev):
      # self.dev = a_dev
      self.active = True
      self.lock = threading.Lock()  # Lock to allow multi-thread access
      self.bytes = bytearray
      self.ix = 0
      self.max = 0
      self.velocities = []
      self.InitVelocities()
      self.functions = [ MidiDumper.TODO,                # 0x
                         MidiDumper.TODO,                # 1x
                         MidiDumper.TODO,                # 2x
                         MidiDumper.TODO,                # 3x
                         MidiDumper.TODO,                # 4x
                         MidiDumper.TODO,                # 5x
                         MidiDumper.TODO,                # 6x
                         MidiDumper.TODO,                # 7x
                         MidiDumper.DumpNoteX,           # 8x
                         MidiDumper.DumpNoteX,           # 9x
                         MidiDumper.DumpAfterTouch,      # Ax
                         MidiDumper.DumpControlChange,   # Bx
                         MidiDumper.DumpProgramChange,   # Cx
                         MidiDumper.DumpChannelPressure, # Dx
                         MidiDumper.DumpPitchBend,       # Ex
                         MidiDumper.DumpSysEx ]          # Fx

      # Dictionary of the last bytestring read from the address/key
      self.sysex = {}
      self.deltaSysex = True

   #=============================================================================
   # Reset the Velocity histogram
   def InitVelocities(self):
      for ix in range( 0, 128 ):
         self.velocities.append(0)

   #=============================================================================
   # Dump and conditionally reset the Velocity histogram
   def DumpVelocities(self, a_reset):
      totalHits = 0
      totalVelocity = 0
      self.lock.acquire()
      for ix in range( 0, 127 ):
         vel = int(self.velocities[ix])
         if vel > 0:
            totalHits += vel
            totalVelocity += ix*vel
            print( '%03d  %d' % (ix, vel) )

         if (a_reset != 0):
            self.velocities[ix] = 0
      self.lock.release()
      
      if totalHits > 0:
         print( 'Average velocity %f' %
           (float(totalVelocity)/float(totalHits)) )

   #=============================================================================
   # Reset the SysEx dictionary so next SysEx is dumped completely
   def ResetSysExDumper(self, a_deltaSysex):
      self.lock.acquire()
      self.sysex = {}
      self.deltaSysex = a_deltaSysex
      self.lock.release()

   #=============================================================================
   # Return a string for MIDI note number (0 to 127)
   def NoteName(self, a_noteNumber):
      return '%s%d(%d)' % (MidiDumper.noteNames[ a_noteNumber % 12 ],
                           (a_noteNumber / 12) - 1,
                           a_noteNumber)

   #=============================================================================
   # Dump a MIDI Note On or Note Off
   def DumpNoteX(self, a_cmd):
      if self.max - self.ix < 3:
         print( 'Note On/Off missing data at offset %d/%d' % (self.ix, self.max))
         self.ix = self.max
      else:
         vel = self.bytes[self.ix+2]
         print( 'Note%s(%d) %s %d' % ('On' if (a_cmd & 0x10) else 'Off',
                                       (a_cmd & 0x0F) + 1,
                                       self.NoteName( self.bytes[self.ix+1] ),
                                       vel) )
         if a_cmd & 0x10:
            # Note on: increment velocity histogram
            self.velocities[vel & 0x7F] += 1
         self.ix += 3

   #=============================================================================
   # Dump a MIDI Control Change
   def DumpControlChange(self, a_cmd):
      if self.max - self.ix < 3:
         print( 'Control Change missing data at offset %d/%d' % (self.ix, self.max))
         self.ix = self.max
      else:
         print( 'CC(%d) %s %d' % ((a_cmd & 0x0F) + 1,
                                  ControllerName( self.bytes[self.ix+1] ),
                                  self.bytes[self.ix+2]) )
         self.ix += 3

   #=============================================================================
   # Dump a MIDI Aftertouch
   def DumpAfterTouch(self, a_cmd):
      if self.max - self.ix < 3:
         print( 'Aftertouch missing data at offset %d/%d' % (self.ix, self.max))
         self.ix = self.max
      else:
         print( 'AT(%d) %d %d' % ((a_cmd & 0x0F) + 1,
                                  self.NoteName( self.bytes[self.ix+1] ),
                                  self.bytes[self.ix+2]) )
         self.ix += 3

   #=============================================================================
   # Dump a MIDI Program Change
   def DumpProgramChange(self, a_cmd):
      if self.max - self.ix < 2:
         print( 'Program Change missing data at offset %d/%d' % (self.ix, self.max))
         self.ix = self.max
      else:
         print( 'PC(%d) %d' % ((a_cmd & 0x0F) + 1,
                               self.bytes[self.ix+1] + 1) )
         self.ix += 2

   #=============================================================================
   # Dump a MIDI Channel Pressure
   def DumpChannelPressure(self, a_cmd):
      if self.max - self.ix < 2:
         print( 'Channel Pressure missing data at offset %d/%d' % (self.ix, self.max))
         self.ix = self.max
      else:
         print( 'ChPr(%d) %d' % ((a_cmd & 0x0F) + 1,
                                 self.bytes[self.ix+1]) )
         self.ix += 2

   #=============================================================================
   # Dump a MIDI Pitch Bend
   def DumpPitchBend(self, a_cmd):
      if self.max - self.ix < 3:
         print( 'Pitch Bend missing data at offset %d/%d' % (self.ix, self.max))
         self.ix = self.max
      else:
         print( 'PB(%d) %d' % ((a_cmd & 0x0F) + 1,
                                128*int(self.bytes[self.ix+1]) +
                                int(self.bytes[self.ix+2]) - 0x2000) )
         self.ix += 3

   #=============================================================================
   # Dump a SysEx message
   def DumpSysEx(self, a_cmd):
      # SysEx response
      # F0 41 10 00 00 00 19 12 03 00 00 00 00 00 00 02 7B F7'
      #                         |--addr---| |--data---|
      if self.max - self.ix < 6:
         print( 'Truncated SysEx message at offset %d/%d' % (self.ix, self.max))
         DumpHex( 'message', self.bytes, self.ix, self.max )
         self.ix = self.max
         return
      if (self.bytes[self.ix+1] != 0x41) or (self.bytes[self.ix+2] != 0x10):
         # TODO: decode standard SysEx
         print( 'We cannot decode the SysEx message at offset %d/%d' % (self.ix, self.max))
         DumpHex( 'message', self.bytes, self.ix, self.max )
         self.ix = self.max
         return
      if self.max - self.ix < 14:
         print( 'Truncated SysEx message at offset %d/%d' % (self.ix, self.max))
         DumpHex( 'message', self.bytes, self.ix, self.max )
         self.ix = self.max
         return
      else:
         dataLen = 0
         for jx in range( self.ix+1, self.max ):
            if self.bytes[jx] == 0xF7:
               dataLen = (jx-1) - (self.ix+12)
               break
         if dataLen <= 0:
            print( 'Unterminated or unknown SysEx message at offset %d/%d' % (self.ix,self.max))
            DumpHex( 'message', self.bytes, self.ix, self.max )
            self.ix = self.max
            return
         elif self.bytes[self.ix+7] != 0x12:
            print( 'SysEx message at offset %d/%d' % (self.ix,self.max))
            DumpHex( 'message', self.bytes, self.ix, self.max )
         else:   
            addr = '%02X:%02X:%02X:%02X' % (self.bytes[self.ix+8],self.bytes[self.ix+9],
                                            self.bytes[self.ix+10],self.bytes[self.ix+11])
            data = bytearray()
            for jx in range( 0, dataLen ):
               data.append( self.bytes[self.ix+12+jx] )

            if self.deltaSysex and (addr in self.sysex) and (dataLen <= len(self.sysex[addr])):
               # We have seen this region before.  Check for changes
               oldData = self.sysex[addr]
               for jx in range( 0, dataLen ):
                  if data[jx] != oldData[jx]:
                     print( 'SysEx %s + 0x%X was 0x%02X, now 0x%02X' %
                            (addr, jx, oldData[jx], data[jx]) )
            else:
               # We haven't seen this region before.  Dump it
               print( '%s has %d bytes' % (addr, dataLen) )
               stg = ''
               for jx in range( 0, dataLen ):
                  if (jx % 16) == 0:
                     if jx > 0:
                        stg += '\n'
                     stg += ('  %04X  ' % jx)
                  stg += ( '%02X ' % self.bytes[self.ix+12+jx] )

               print( stg )
            
            if self.deltaSysex:
               self.sysex[addr] = data

         self.ix += 12 + dataLen + 2

   #=============================================================================
   # Dump stuff we don't decode yet, or orphan data bytes
   def TODO(self, a_cmd):
      print( 'Unexpected byte 0x%02X at offset %d/%d' % (a_cmd, self.ix, self.max) )
      self.ix += 1

   #=============================================================================
   # Dump received MIDI
   def DumpInput(self, a_bytes):
      self.lock.acquire()
      self.bytes = a_bytes
      self.ix = 0
      self.max = len(a_bytes)

      # print( 'DumpReply of %d bytes' % self.max )
      while self.ix < self.max:
         cmd = self.bytes[self.ix]
         self.functions[ cmd >> 4 ]( self, cmd )
      self.lock.release()

#=============================================================================
# Send a SysEx read of a_length data bytes from a_startAddr (list of four int)
def SendSysEx( a_dev, a_startAddr, a_length ):
   # Arithmetic is easier on a binary address...
   addr = ((a_startAddr[0] << 21) | (a_startAddr[1] << 14) |
           (a_startAddr[2] << 7) | a_startAddr[3])

   print( 'Read %02X:%02X:%02X:%02X 0x%X bytes' %
          (a_startAddr[0], a_startAddr[1], a_startAddr[2], a_startAddr[3],
           a_length ) )

   bytes = bytearray()
   bytes.append( 0xF0 )     # Sysex to Roland device
   bytes.append( 0x41 )
   bytes.append( 0x10 )
   bytes.append( 0x00 )     # Model FP-90
   bytes.append( 0x00 )
   bytes.append( 0x00 )
   bytes.append( 0x19 )
   bytes.append( 0x11 )     # function is read

   a1 = (addr >> 21) & 0x7F
   a2 = (addr >> 14) & 0x7F
   a3 = (addr >> 7) & 0x7F
   a4 = addr & 0x7F
   bytes.append( a1 )       # address
   bytes.append( a2 )
   bytes.append( a3 )
   bytes.append( a4 )
    
   l1 = (a_length >> 21) & 0x7F
   l2 = (a_length >> 14) & 0x7F
   l3 = (a_length >> 7) & 0x7F
   l4 = a_length & 0x7F
   bytes.append( l1 )        # length
   bytes.append( l2 )
   bytes.append( l3 )
   bytes.append( l4 )

   checksum = (128 - (a1+a2+a3+a4 + l1+l2+l3+l4)) & 0x7F
   bytes.append( checksum )
   bytes.append( 0xF7 )     # end of Sysex

   os.write( a_dev, bytes )

#=============================================================================
# Comment
def CmdComment( a_dev, a_cmd ):
   return

#=============================================================================
# Command: Read Common SysEx
def CmdReadSysEx( a_dev, a_cmd ):
   # Length is wierd: too small gets 01xxxxxx only, too large includes 03xxxxxx
   # There seems to be no value that gets 01 and 02 but not 03
   SendSysEx( a_dev, [0x01, 0x00, 0x00, 0x00],0x40000 )
   sleep( 0.5 )
   SendSysEx( a_dev, [0x01, 0x00, 0x01, 0x00],0x40000 )
   sleep( 0.5 )
   SendSysEx( a_dev, [0x01, 0x00, 0x02, 0x00],0x40000 )
   sleep( 0.5 )

   SendSysEx( a_dev, [0x02, 0x00, 0x00, 0x00],0x4000 )
   if len(a_cmd[0]) > 1:
      sleep( 0.5 )
      SendSysEx( a_dev, [0x02, 0x10, 0x00, 0x00],0x4000 )
   if len(a_cmd[0]) > 2:
      sleep( 0.5 )
      SendSysEx( a_dev, [0x03, 0x00, 0x00, 0x00],0x40000 )

#=============================================================================
# Command: Read Specific SysEx
def CmdReadSysExByAddr( a_dev, a_cmd ):
   if len(a_cmd) < 3:
      print( 'Must specify an address nn:nn:nn:nn and a length' )
      return

   addrStr = a_cmd[1].split(':')
   if len(addrStr) != 4:
      print( 'Must specify an address as nn:nn:nn:nn' )
      return
   addr = [ AsInt( addrStr[0], 0 ), AsInt( addrStr[1], 0 ), 
            AsInt( addrStr[2], 0 ), AsInt( addrStr[3], 0 ) ]
   length = AsInt( a_cmd[2], -1 )

   SendSysEx( a_dev, addr, length )

#=============================================================================
# Command: Reset the SysEx dumping information
def CmdResetSysExDump( a_dev, a_cmd ):
   global g_midiDumper
   print( 'Reset SysEx map' )
   g_midiDumper.ResetSysExDumper( len(a_cmd) > 1 )

#=============================================================================
# Command: Send a SysEx Identify
def CmdSysId( a_dev, a_cmd ):
   SendMidi( a_dev, [ 0xF0, 0x7E, 0x10, 0x06, 0x01, 0xF7 ] )

#=============================================================================
# Command: Send Control Change
def CmdSendControlChange( a_dev, a_cmd ):
   if len(a_cmd) >= 3:
      cc = AsInt( a_cmd[1], 1 )
      vv = AsInt( a_cmd[2], 0 )
      channel = g_channel if (len(a_cmd) < 4) else AsInt( a_cmd[3], g_channel )
      SendMidi( a_dev, [ 0xB0 + channel - 1, cc, vv ] )

#=============================================================================
# Command: Send Program Change
def CmdSendProgramChange( a_dev, a_cmd ):
   if len(a_cmd) >= 2:
      vv = AsInt( a_cmd[1], 1 )
      channel = g_channel if (len(a_cmd) < 3) else AsInt( a_cmd[2], g_channel )
      SendMidi( a_dev, [ 0xC0 + channel - 1, vv ] )

#=============================================================================
# Command: Send Pitch Bend
def CmdSendPitchBend( a_dev, a_cmd ):
   if len(a_cmd) >= 2:
      vv = AsInt( a_cmd[1], 1 ) + 0x2000
      if vv < 0:
         vv = 0
      channel = g_channel if (len(a_cmd) < 3) else AsInt( a_cmd[2], g_channel )
      SendMidi( a_dev, [ 0xE0 + channel - 1, vv & 127, vv >> 7 ] )

#=============================================================================
# Send note on NN at velocity VV for duration X
def CmdSendNoteOn( a_dev, a_cmd ):
   if len(a_cmd) >= 3:
      note = AsInt( a_cmd[1], 64 )
      vel = AsInt( a_cmd[2], 64 )
      dur = 0 if (len(a_cmd) < 4) else AsInt( a_cmd[3], 64 )

      channel = g_channel if (len(a_cmd) < 5) else AsInt( a_cmd[4], g_channel )
      SendMidi( a_dev, [ 0x90 + channel - 1, note, vel ] )
      if dur > 0:
         sleep( float(dur) / 1000.0 )
         SendMidi( a_dev, [ 0x80 + channel - 1, note, 0 ] )

#=============================================================================
# Send note off NN at velocity VV
def CmdSendNoteOff( a_dev, a_cmd ):
   if len(a_cmd) >= 3:
      note = AsInt( a_cmd[1], 64 )
      vel = AsInt( a_cmd[2], 64 )

      channel = g_channel if (len(a_cmd) < 4) else AsInt( a_cmd[4], g_channel )
      SendMidi( a_dev, [ 0x80 + channel - 1, note, vel ] )

#=============================================================================
# Set the default MIDI transmit channel
def CmdSetChannel( a_dev, a_cmd ):
   global g_channel
   if len(a_cmd) >= 2:
      g_channel = AsInt( a_cmd[1], g_channel )
      print( 'Default channel is %d' % g_channel )

#=============================================================================
# Dump the Velocity histogram
def CmdShowVelocity( a_dev, a_cmd ):
   global g_midiDumper
   g_midiDumper.DumpVelocities( len(a_cmd) >= 2 )

#=============================================================================
# List tone categories
def CmdListCategories( a_dev, a_cmd ):
   g_tones.ShowCategories()

#=============================================================================
# List tones in the current category
def CmdListTones( a_dev, a_cmd ):
   cat = ''
   if (len(a_cmd) > 1):
      cat = a_cmd[1]
      if (len(a_cmd) > 2):
         cat += ' ' + a_cmd[2]
   g_tones.ShowTones(cat)

#=============================================================================
# List tones in the current category by name
def CmdListTonesByName( a_dev, a_cmd ):
   cat = ''
   if (len(a_cmd) > 1):
      cat = a_cmd[1]
      if (len(a_cmd) > 2):
         cat += ' ' + a_cmd[2]
   g_tones.ShowTonesByName(cat)

#=============================================================================
# Select the a tone by number, changing category to match
def CmdSelectTone( a_dev, a_cmd ):
   if (len(a_cmd) > 1):
      tone = AsInt( a_cmd[1], -1 )
      if tone >= 0:
         g_tones.SelectTone( tone )
   else:
      g_tones.ShowCurrentTone()

#=============================================================================
# Select the next tone in the current category
def CmdNextTone( a_dev, a_cmd ):
   g_tones.SelectNextTone( 1 )

#=============================================================================
# Select the previous tone in the current category
def CmdPreviousTone( a_dev, a_cmd ):
   g_tones.SelectNextTone( -1 )

#=============================================================================
# Set or get a tone variable, select that tone 
def CmdToneVar( a_dev, a_cmd ):
   g_tones.ToneVar( a_cmd )

#=============================================================================
# Class to drive "testcc"
class TestCC:
   def __init__( self, a_title, a_cc, a_values ):
      self.title = a_title
      self.cc = a_cc
      self.values = a_values

   def DoIt( self, a_dev ):
      for val in self.values:
         SendMidi( a_dev, [ 0xB0 + g_channel - 1, self.cc,  val ] )
         if (g_channel != MIDI_CHANNEL):
            SendMidi( a_dev, [ 0x90 + g_channel - 1, 64, 127 ] )
            sleep( 0.1 )
            SendMidi( a_dev, [ 0x80 + g_channel - 1, 64, 127 ] )
            sleep( 0.5 )
            SendMidi( a_dev, [ 0x90 + g_channel - 1, 32, 127 ] )
            sleep( 0.1 )
            SendMidi( a_dev, [ 0x80 + g_channel - 1, 32, 127 ] )
            sleep( 0.5 )
            SendMidi( a_dev, [ 0x90 + g_channel - 1, 64, 127 ] )
            sleep( 0.1 )
            SendMidi( a_dev, [ 0x80 + g_channel - 1, 64, 127 ] )
            sleep( 0.5 )

         cmd = raw_input( '%s: Set CC %s to %d.  Press Enter to continue' %
                          (self.title, ControllerName(self.cc), val) )

ccTests = [
   #TestCC( 'Reset Controllers', 120, [0] ),
   #TestCC( 'Volume',     7,  [10, 127] ),     # all do this
   #TestCC( 'Pan',        10, [0, 64] ),       # GM, some E.Piano
   #TestCC( 'Expression', 11, [10, 127] ),     # all do this
   #TestCC( 'Reverb', 91, [127, 0] ),          # no effect that I can hear
   #TestCC( 'Chorus', 93, [127, 0] ),          # works on various
   #TestCC( 'CC 92', 92, [127, 64, 0] ),       # no effect that I can hear
   #TestCC( 'CC 94', 94, [127, 64, 0] ),       # no effect that I can hear

   #TestCC( 'Vibrato rate',  76, [64] ),       # affects rate, high values are silly fase
   #TestCC( 'Modulation', 1,  [127, 64, 0] ),  # no effect on Piano 1-4; vibrato on most other tones
   #TestCC( 'Vibrato rate',  76, [10] ),
   #TestCC( 'Modulation', 1,  [127, 64, 0] ),
   #TestCC( 'Vibrato rate',  76, [127] ),
   #TestCC( 'Modulation', 1,  [127, 64, 0] ),
   #TestCC( 'Vibrato depth', 77, [127, 0, 64] ), # high value can get funky
   #TestCC( 'Vibrato delay', 78, [64, 0, 127] ),

   TestCC( 'Effect 1', 12,  [127, 64, 0] ),   # tremelo/chorus/detune/wah on some "E.Piano"
                                               # Leslie on/off on "Organ" electronic organs
                                               # but NOT on the GM pianos or organs
                                               # Seems to match modulationSpeed (E.pianos and pads)
                                               # or rotarySpeed (E.organs) in Registration
                                               # CC12 sent BY piano when one of these registrations
                                               # is selected, with scaled rotarySpeed/modulationSpeed
                                               # CC12 sent BY the piano if you ADJUST these
                                               # but NOT when you change between Tones

   #TestCC( 'Resonance', 71, [0] ),            # not main Pianos.  Works on at least some other tones
   #TestCC( 'Cutoff', 74, [0, 127, 64] ),
   #TestCC( 'Resonance', 71, [127] ),
   #TestCC( 'Cutoff', 74, [0, 127, 64] ),
   #TestCC( 'Resonance', 71, [64] ),
   #TestCC( 'Cutoff', 74, [0, 127, 64] ),

   #TestCC( 'Attack',  73, [0, 127, 64] ),      # not main Pianos.  Works on at least some other tones
   #TestCC( 'Decay',   75, [0, 127, 64] ),
   #TestCC( 'Release', 72, [0, 127, 64] ),

   # Short times (5 to 10) are most plausible.
   # But at least in poly mode, attack is on the pitch of the previous
   # note and swoops from there.  Not realistic for bass at least.
   #TestCC( 'Portamento on', 65,  [127] ),      # not main Pianos.  Works on at least some other tones
   #TestCC( 'Portamento time', 5,  [10, 0, 127] ),
   #TestCC( 'Portamento off', 65,  [0] ),
   TestCC( 'Reset All', 121, [0] )
]

#=============================================================================
# Test the effect of various MIDI CC on the current tone
def CmdTestCC( a_dev, a_cmd ):
   nTones = AsInt( a_cmd[1], 1 ) if len(a_cmd) > 1 else 1
   while nTones > 0:
      for test in ccTests:
         test.DoIt( a_dev )
      g_tones.SelectNextTone( 1 )
      nTones -= 1

#=============================================================================
# Dictionary of command handlers
KEY_COMMANDS = {}

#=============================================================================
# Process a text command.
# Return True to continue processing, False to quite
def ProcessCommand( a_dev, a_command ):
   cmd = a_command.split()
   if len(cmd) == 0:
      CmdNextTone( a_dev, cmd )

   elif cmd[0] == 'quit':
      return False
      
   elif cmd[0] in KEY_COMMANDS:
      KEY_COMMANDS[cmd[0]]( a_dev, cmd )

   else:
      print( 'Unknown command "%s".  Try "help"' % a_command )
      #for ch in a_command:
      #   print( '%02X' % ord(ch) )
      
   return True

g_tones = ToneList()

#=============================================================================
# Worker thread to receive and dump MIDI input
def Dumper(a_dev, a_dumper):
   print( 'Worker starting' )
   
   bytes = bytearray()
   while a_dumper.active:
      r, w, e = select.select( [ a_dev, sys.stdin ], [], [], 0.2 )
      if (len(r) == 0) and (len(bytes) > 0):
         # timeout: dump any pending input
         a_dumper.DumpInput(bytes)
         del bytes[:]
         
      if a_dev in r:
         chunk = bytearray( os.read( a_dev, 100000 ) )
         bytes.extend( chunk )

   print( 'Worker exiting' )
   return

#=============================================================================
# Add a command to the dictionary and help string
def AddCommand( a_name, a_handler, a_help = '' ):
   global KEY_COMMANDS
   global HELP_STRING
   if a_handler:
      KEY_COMMANDS[ a_name ] = a_handler
   if a_help:
      HELP_STRING += a_help + '\n'

#=============================================================================
# Initialize the command dictionary and help string
def InitCommands():
   global HELP_STRING
   HELP_STRING = 'Command are:\n'

   AddCommand( 'help', CmdHelp,           '"help" or "?" to show this list of commands.' )
   AddCommand( '?',    CmdHelp )
   AddCommand( ';',    CmdComment,        '"; xxxxx" comment line xxxx.' )
   
   # SysEx reads
   AddCommand( '/', CmdReadSysEx,         '"/"   do a SysEx poll of short live data.' )
   AddCommand( '//', CmdReadSysEx,        '"//"  do a SysEx poll of all live data.' )
   AddCommand( '///', CmdReadSysEx,       '"///" do a SysEx poll of persisted (03) data.' )
   AddCommand( 'rdsys', CmdReadSysExByAddr,'"rdsys nn:nn:nn:nn ll" do a SysEx read of the specified address.' )
   AddCommand( 'rsysex', CmdResetSysExDump,'"rsysex {x}" reset the SysEx history so next is dumped completely.\n'
                                           '   If any value x is specified, track changes to SysEx regions, else\n'
                                           '   dump the complete SysEx each time.' )
   AddCommand( 'sysid', CmdSysId,          '"sysid" send a SysEx Identify.' )
   
   # Send MIDI
   AddCommand( 'cc', CmdSendControlChange, '"cc nn vv {ch}" send a MIDI Control Change for control nn, value vv.\n'
                                           '   If {ch} is specified, send on that channel, else use the default.' )
   AddCommand( 'pc', CmdSendProgramChange, '"pc pp {ch}" send a MIDI Program Change to program pp.' )
   AddCommand( 'pb', CmdSendPitchBend,     '"pb bbbb {ch}" send a MIDI Pitch Bend with signed value bbbb.' )
   AddCommand( 'non', CmdSendNoteOn,       '"non nn vv {dd} {ch}" send a MIDI NoteOn for note nn, velocity vv,\n'
                                           '   and duration dd (msec).  If dd is 0 or omitted, note is left on.' )
   AddCommand( 'nof', CmdSendNoteOff,      '"nof nn vv {ch}" send a MIDI NoteOff for note nn, velocity vv.' )
   AddCommand( 'ch', CmdSetChannel,        '"ch nn" set the default MIDI channel to nn.' )

   # Misc
   AddCommand( 'vel', CmdShowVelocity,     '"vel {x}" show histogram of note-on velocity.\n'
                                           '   Include parameter to reset histogram data.' )

   # Tone Selection Spreadsheet
   AddCommand( 'cat', CmdListCategories,   '"cat" show a list of tone categories' )
   AddCommand( 'l', CmdListTones,          '"l {cat}" list the tones in category {cat} by location.' )
   AddCommand( 'L', CmdListTonesByName,    '"L {cat}" list the tones in category {cat} by name.' )
   AddCommand( 't', CmdSelectTone,         '"t nnn" to select tone nnn.' )
   AddCommand( 'n', CmdNextTone,           '"n" or Enter to select the next tone in the current category.' )
   AddCommand( 'p', CmdPreviousTone,       '"p" select the previous tone in the current category.' )
   AddCommand( 'a', CmdToneVar,            '"a nnn" select tone nnn and save it in variable "a"\n.'
                                           '"   Omit nnn to select the tone previously saved in "a".\n'
                                           '"   b", "c", and "d" operate like "a" on distinct variables.' )
   AddCommand( 'b', CmdToneVar )
   AddCommand( 'c', CmdToneVar )
   AddCommand( 'd', CmdToneVar )
   AddCommand( 'testcc', CmdTestCC,        '"testcc" Test the effect of various MIDI CC.' )

   HELP_STRING += '"quit" to quit.\n'


#=============================================================================
# Display the command list
def CmdHelp( a_dev, a_cmd ):
   print( HELP_STRING )

#=============================================================================
# If the specified file is a MIDI file, dump it and return True.
# Else return false
def TryDecodeMidiFile( a_fileName ):
   retval = False
   with open( a_fileName, 'rb' ) as midiFile:
      # MIDI file begins with "MThd"
      cookie = midiFile.read(4)
      if cookie == 'MThd':
         # Read the remainder of the file, decode as MIDI
         retval = True
         data = bytearray( midiFile.read() )
         #DumpHex( a_fileName, data, 0, 512 )
         midiDumper = MidiDumper( -1 )
         midiDumper.DumpInput( data )
      midiFile.close()
   return retval

#=============================================================================
#
def main():
   # Tone spreadsheet is optional
   if len(sys.argv) > 1:
      if TryDecodeMidiFile( sys.argv[1] ):
         # After decoding the file, just exit with no MIDI device interaction
         return

      g_tones.ProcessToneList( sys.argv[1] )

   dev = os.open( MIDI_DEVICE, os.O_RDWR )
   if dev < 0:
      print('Cannot open %s' % MIDI_DEVICE )
      return
      
   print('Opened %s as dev %d' % (MIDI_DEVICE, dev) )
   g_tones.dev = dev

   # Initialize our command set
   InitCommands()

   # Create a MIDI dumper thread
   global g_midiDumper
   g_midiDumper = MidiDumper( dev )
   midiThread = threading.Thread(target=Dumper, name='MidiRx', args=(dev,g_midiDumper))
   midiThread.daemon = True
   midiThread.start()

   readline.clear_history()
   while True:
      cmd = raw_input('>')
      if ProcessCommand( dev, cmd.strip() ) == False:
         break
   
   # Tell the worker to exit, and wait for it to do so
   g_midiDumper.active = False
   midiThread.join()

   os.close(dev)

if __name__ == "__main__":
   main()
