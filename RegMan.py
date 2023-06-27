#!/usr/bin/python
#
# RegMan.py: Convert between Roland FP60/FP90 UPG files and CSV
#
# Python 2.7
#
# Written by John Hartman
#
# Updated 15 January 2020
#
# TODO: This version uses raw integers from the UPG for enumerated functions.
# We might consider text values for nicer editing
#   keyboardMode     single, split, dual
#   splitPoint       C3, F#3 etc
#   damperPedalPart  both, right/Tone1, left/Tone2
#   centerPedalPart  (as above)
#   leftPedalPart    (as above)
#   centerPedalFunc  Sustenuto, Play/stop, Layer, Expression, Master expression,
#                    Bend up, Bend down, Modulation, Microphone double,
#                    Microphone echo, Rotary on/off
#   leftPedalFunc    (as above, but "Soft" instead of "Sustenuto"
#   rotarySpeed      on, off
# But some of these are long enough that they are a pain without a drop-list.
#
import sys
import string
import time
import csv
import json

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
      self.currentCategory = ''         # Select category
      self.currentTone = 0              # Selected tone index
      self.tones = []                   # List tones, since their names may not be unique
      self.toneByLoc = {}               # Dictionary of tone indexes by location
      self.toneByName = {}              # Dictionary of tone indexes by name
      self.toneByBank = {}              # Dictionary of tone indexes by bank and program change

   #=============================================================================
   # Read the tone list CSV file
   #"Location","Name","MSB","LSB","PC","Category"
   def ProcessToneList( self, a_fileName ):
      print( 'Processing tone list "%s"' % a_fileName )

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

               self.toneByLoc[location]  = index
               # NOTE: lookup by name may not be unique.  Use the first one
               # (The only duplicate on FP-90 version 1.05 is "Orchestra", 
               # which appears as "Strings:7" and "GM2:128")
               if name in self.toneByName:
                  print( 'Duplicate name %s' % name )
               else:
                  self.toneByName[name]     = index

               # Program Change value minus 1, per MIDI usage
               bankSelect = '%d:%d:%d' % (int(row[2]), int(row[3]), int(row[4]) - 1)
               self.toneByBank[bankSelect]  = index

               if len(self.currentCategory) == 0:
                  self.currentCategory = category
                  self.currentTone = index
               index += 1

g_tones = ToneList()

#=============================================================================
# Names of the piano's Tone group buttons
g_groupNames = [ 'Piano', 'E.Piano', 'Strings', 'Organ', 'Pad', 'Other' ]

# Names of Registration items in the UPG, in the order of the UPG
g_itemNames = [
            'name',
            'ambience',
            'keyTouch',
            'keyTranspose',
            'songTranspose',
            'keyboardMode',
            'singleToneMSB',
            'singleToneLSB',
            'singleTonePC',
            'splitLowerToneMSB',
            'splitLowerToneLSB',
            'splitLowerTonePC',
            'splitOctaveShift',
            'splitUpperOctaveShift',
            'splitPoint',
            'splitBalance',
            'dualTone2MSB',
            'dualTone2LSB',
            'dualTone2PC',
            'dualOctaveShift',
            'dualTone1OctaveShift',
            'dualBalance',
            'twinPianoMode',
            'damperPedalPart',
            'centerPedalFunc',
            'leftPedalFunc',
            'midiTxCh',
            'rotarySpeed',
            'modulationSpeed',
            'upperVolume',
            'lowerVolume',
            'micCompSw',
            'micCompType',
            'micDoublingSw',
            'micDoublingType',
            'micDoublingWidth',
            'micDoublingLevel',
            'micEchoSw',
            'micEchoType',
            'micEchoLevel',
            'centerPedalPart',
            'leftPedalPart',
            'registrationTxCh',
            'registrationBankMSB',
            'registrationBankLSB',
            'registrationPC'
           ]

# Names of Registration items in the UPG, not processed explicitly, grouped
# and ordered to ease editing of the spreadsheet
g_miscItemNames = [
            #'name',

            #'singleToneMSB',
            #'singleToneLSB',
            #'singleTonePC',

            #'splitLowerToneMSB',
            #'splitLowerToneLSB',
            #'splitLowerTonePC',

            #'dualTone2MSB',
            #'dualTone2LSB',
            #'dualTone2PC',

            'keyboardMode',
            'splitOctaveShift',
            'splitUpperOctaveShift',
            'splitPoint',
            'dualOctaveShift',
            'dualTone1OctaveShift',

            'damperPedalPart',
            'centerPedalPart',
            'centerPedalFunc',
            'leftPedalPart',
            'leftPedalFunc',

            'rotarySpeed',
            'modulationSpeed',
            'upperVolume',
            'lowerVolume',

            'ambience',
            'keyTouch',
            'keyTranspose',
            'songTranspose',

            'midiTxCh',
            'registrationTxCh',
            'registrationBankMSB',
            'registrationBankLSB',
            'registrationPC',

            'micCompSw',
            'micCompType',
            'micDoublingSw',
            'micDoublingType',
            'micDoublingWidth',
            'micDoublingLevel',
            'micEchoSw',
            'micEchoType',
            'micEchoLevel',

            'splitBalance',
            'dualBalance',
            'twinPianoMode'
           ]

#=============================================================================
# Read the UPG file and generate a CSV
def ConvertRegistrationUPG( a_inFileName, a_outFileName ):
   print( 'Processing Registration UPG "%s" as "%s"' % (a_inFileName, a_outFileName) )

   with open( a_inFileName, 'rb' ) as upgFile:
      data = json.load( upgFile )
      print( 'Title is %s' % data['title'] )
      print( 'Version is %s' % data['formatVersion'] )
      print( 'Pedal shift is %s' % data['registrationPedalShift'] )

      with open( a_outFileName, 'wb' ) as csvFile:
         writer = csv.writer( csvFile, dialect='excel', quoting=csv.QUOTE_NONNUMERIC )

         # Create a header row
         header = []
         header.append( 'Location' )
         header.append( 'name' )
         header.append( 'singleTone' )
         header.append( 'splitLowerTone' )
         header.append( 'dualTone2' )
         header.extend( g_miscItemNames )

         # Append Title, version, and pedal shift as fake titles to get them
         # in the CSV for round-trip to UPG
         header.append( data['title'] )
         header.append( data['formatVersion'] )
         header.append( data['registrationPedalShift'] )

         writer.writerow( header )

         group = 0
         ix = 1
         regs = data[ 'registration' ]
         print( 'Has %d registrations' % len(regs) )
         for reg in regs:
            print( 'Reg (%s,%d) "%s is (%d,%d,%d)"' %
                   (g_groupNames[group], ix, reg['name'],
                    reg['singleToneMSB'], reg['singleToneLSB'], reg['singleTonePC'])
                 )

            # Write the item as a row of CSV
            row = []
            row.append( '(%s,%d)' % (g_groupNames[group], ix) )

            row.append( reg['name'] )

            # Append the names of the Tones, computed from the MIDI values
            single = '%d:%d:%d' % (reg["singleToneMSB"], reg["singleToneLSB"], reg["singleTonePC"])
            row.append( g_tones.tones[ g_tones.toneByBank[single] ].name )

            splitLower = '%d:%d:%d' % (reg["splitLowerToneMSB"], reg["splitLowerToneLSB"], reg["splitLowerTonePC"])
            row.append( g_tones.tones[ g_tones.toneByBank[splitLower] ].name )

            dual = '%d:%d:%d' % (reg["dualTone2MSB"], reg["dualTone2LSB"], reg["dualTone2PC"])
            row.append( g_tones.tones[ g_tones.toneByBank[dual] ].name )

            # Append the remaining items that don't need special processing
            for elementName in g_miscItemNames:
               row.append( reg[elementName] )

            writer.writerow( row )

            ix += 1
            if ix >=6:
               group += 1
               ix = 1

         csvFile.close()
      upgFile.close()

#=============================================================================
# Dump a row to a UPG file
def DumpUGP_Row( a_file, a_row ):
   ix = 1
   str = ''
   for name in g_itemNames:
      str += '            "%s": %s' % (name, a_row[name])
      if ix < len(g_itemNames):
         str += ',\n'
      else:
         str += '\n'
      ix += 1

   a_file.write( str )

#=============================================================================
# Return (bankMSB, bankLSB, PC) for the specified Tone name
def MidiForToneName( a_toneName ):
   if a_toneName in g_tones.toneByName:
      tone = g_tones.tones[ g_tones.toneByName[a_toneName] ]
      return tone.msb, tone.lsb, tone.pc - 1

   else:
      print( 'Error: Tone "%s" not known' % a_toneName )
      return 0,0,0

#=============================================================================
# Read the CSV file and generate a UPG
def ConvertRegistrationCSV( a_inFileName, a_outFileName ):
   print( 'Processing Registration CSV "%s" as "%s"' % (a_inFileName, a_outFileName) )

   # We can't use json.dump, as it won't let us control the order of the
   # output lines, since real json doesn't care.
   # But the FP-90 MAY care, and we want some degree of readability in any case.
   #    json.dump( regs, upgFile, indent=4, separators=(',', ': ') )
   with open( a_inFileName, 'rb' ) as csvFile:
      with open( a_outFileName, 'wb' ) as upgFile:

         # When we converted the UPG to a CSV, we appended "fake headers" for
         # title, formatVersion, and registrationPedalShift.
         # Harvest their values (the last three header cells) here
         headers = csvFile.readline().strip().replace( '"', '' ).split(',')
         if headers[ len(headers)-4 ] == g_miscItemNames[ len(g_miscItemNames)-1 ]:
            # We have three values after the last "real" item
            pedalShift = headers.pop()
            version = headers.pop()
            title = headers.pop()
         else:
            # Backward compatible with versions that didn't add fake headers
            print( 'Using default title/version/shift' )
            title = 'PianoRegistration'
            version = 2
            pedalShift = 0

         # Give the headers to the dictionary reader
         reader = csv.DictReader( csvFile, fieldnames = headers, dialect='excel' )

         # Write the part before the registrations.
         upgFile.write( '{\n'
                        '    "title": "%s",\n'
                        '    "formatVersion": %s,\n'
                        '    "registrationPedalShift": %s,\n'
                        '    "registration": [\n' % (title, version, pedalShift ) )
         rowNumber = 1
         for row in reader:
            location = row['Location']
            name = row['name']
            print( '%2d) %-12s is "%s"' % (rowNumber, location, name) )

            # Since computed data and user data are interleaved, we add the
            # computed items to the dictionary, and then output the desired
            # portions of the dictionary using g_itemNames to specify order

            # Excel CSV escapes " as "".  CSV reader/writer handles that.
            # JSON escapes " and \ with a backslash.  JSON Reader handles that,
            # but we are writing manually so need to do it ourself.
            name = name.replace( '\\', '\\\\' )
            name = name.replace( '"',  '\\"' )
            row['name'] = '"' + name + '"'

            msb, lsb, pc = MidiForToneName( row['singleTone'] )
            row['singleToneMSB'] = msb
            row['singleToneLSB'] = lsb
            row['singleTonePC']  = pc

            msb, lsb, pc = MidiForToneName( row['splitLowerTone'] )
            row['splitLowerToneMSB'] = msb
            row['splitLowerToneLSB'] = lsb
            row['splitLowerTonePC']  = pc

            msb, lsb, pc = MidiForToneName( row['dualTone2'] )
            row['dualTone2MSB'] = msb
            row['dualTone2LSB'] = lsb
            row['dualTone2PC']  = pc

            if rowNumber != 1:
               upgFile.write( '        },\n' )
            upgFile.write( '        {\n' )

            DumpUGP_Row( upgFile, row )
            rowNumber += 1

         # Finish the file
         upgFile.write( '        }\n'
                        '    ]\n'
                        '}\n' )
         upgFile.close()

      csvFile.close()

#=============================================================================
# Read the Tone list CSV file and generate a JSON version
def ConvertToneList( a_inFileName, a_outFileName ):
   print( 'Processing Tone list CSV "%s" as "%s"' % (a_inFileName, a_outFileName) )

   with open( a_inFileName, 'rb' ) as csvFile:
      with open( a_outFileName, 'wb' ) as jsonFile:

         tones = []
         reader = csv.DictReader( csvFile, dialect='excel' )
         for row in reader:
            tones.append(row)

         json.dump( tones, jsonFile, indent=4, separators=(',', ': ') )
         jsonFile.close()

      csvFile.close()

#=============================================================================
#
def main():
   # Tone spreadsheet is optional
   if len(sys.argv) > 1:
      g_tones.ProcessToneList( sys.argv[1] )

      if len(sys.argv) <= 2:
         # Convert the Tone List to JSON
         outFile = sys.argv[1] + '.json'
         ConvertToneList( sys.argv[1], outFile )

      else:
         name = sys.argv[2].split('.')
         if name[1].lower() == 'upg':
            # Convert a UPG file into a CSV
            if len(sys.argv) > 3:
               outFile = sys.argv[3]
            else:
               outFile = name[0] + '.csv'
            ConvertRegistrationUPG( sys.argv[2], outFile )

         elif name[1].lower() == 'csv':
            # Convert a CSV file into a UPG
            if len(sys.argv) > 3:
               outFile = sys.argv[3]
            else:
               outFile = name[0] + '.upg'
            ConvertRegistrationCSV( sys.argv[2], outFile )
         else:
            print( 'Error: Must specify a UPG or CSV file' )

   else:
      print( 'To convert a UPG file to a CSV for editing:' )
      print( '  RegMan.py "Roland FP-90 MIDI Voices.csv" infile.upg outfile.csv' )
      print( 'To convert a CSV file to a UPG:' )
      print( '  RegMan.py "Roland FP-90 MIDI Voices.csv" infile.csv outfile.upg' )
      print( 'If the outfile is omitted, "infile" is used, adding the appropriate extension' )

if __name__ == "__main__":
   main()

