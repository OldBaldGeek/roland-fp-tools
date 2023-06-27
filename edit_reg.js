// edit_reg.js - JavaScript code to edit Registration (.UPG) files from
// Roland FP-60 and FP-90 pianos.
//
// Copyright (c) 2020 by JOhn Hartman
//
// edit 28 February 2020

//-----------------------------------------------------------------------------
// Names of the piano's Tone group buttons
var g_groupNames = [ 'Piano', 'E.Piano', 'Strings', 'Organ', 'Pad', 'Other' ];

//-----------------------------------------------------------------------------
// Names of Registration items in the UPG file, in the order of the file
// TODO: these don't seem to be currently used by our code, but hang onto them...
var g_itemNames = [
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
];

//-----------------------------------------------------------------------------
// Default values for Registration items
var g_defaultRegValues = {
   "name": "(none)",
   "singleTone"    : "ConcertPiano",    // Generated from MSB/LSB/PC
   "splitLowerTone": "Ac.Bass wRel",    // Generated from MSB/LSB/PC
   "dualTone2"     : "Strings forI",    // Generated from MSB/LSB/PC

   "keyboardMode": 0,
   "splitOctaveShift": 0,
   "splitUpperOctaveShift": 0,
   "splitPoint": 54,
   "dualOctaveShift": 0,
   "dualTone1OctaveShift": 0,

   "damperPedalPart": 0,
   "centerPedalPart": 0,
   "centerPedalFunc": 0,
   "leftPedalPart": 0,
   "leftPedalFunc": 0,

   "rotarySpeed": 0,
   "modulationSpeed": 0,
   "upperVolume": 100,
   "lowerVolume": 100,

   "ambience": 2,
   "keyTouch": 50,
   "keyTranspose": 0,
   "songTranspose": 0,

   "midiTxCh": 1,
   "registrationTxCh": 0,
   "registrationBankMSB": 0,
   "registrationBankLSB": 0,
   "registrationPC": 0,

   "micCompSw": 0,
   "micCompType": 1,
   "micDoublingSw": 0,
   "micDoublingType": 0,
   "micDoublingWidth": 1,
   "micDoublingLevel": 10,
   "micEchoSw": 0,
   "micEchoType": 0,
   "micEchoLevel": 5,

   "splitBalance": 0,
   "dualBalance": -5,
   "twinPianoMode": 1
};

// List of Tones read from the Tone spreadsheet
g_toneList = null;

// Name of the file from which we read Registration data
g_filename = '';

// Object with the Registration data
g_upg = null;

// Currently selected row index, or -1 if none selected
g_selectedRow = -1;

// Used to validat sessionData
const g_sessionDataCookie = 'Roland FP-60 Registration Data version 1.00';

// Change flag object
g_changeFlag = null;

//-----------------------------------------------------------------------------
// Class to implement change flag
class ChangeFlag
{
   constructor( a_indicatorID )
   {
      this.indicator = document.getElementById( a_indicatorID );
      this.defaultBG = this.indicator.style.backgroundColor;
      this.changed = false;
   }

   // Set the change flag, and the color of the indicator
   Set()
   {
      this.changed = true;
      this.indicator.style.backgroundColor = 'red';
   }
   
   // Clear the change flag, and the color of the indicator
   Clear( a_changed )
   {
      this.changed = false;
      this.indicator.style.backgroundColor = this.defaultBG;
   }

   // Return "changed" state
   Changed()
   {
      return this.changed;
   }
}

//-----------------------------------------------------------------------------
// Class to deal with Tone list
class ToneList
{
   constructor(a_tones)
   {
      // Create maps of the Tone list indexed by Name and Bank
      this.toneArray = a_tones;
      this.toneByName = {};
      this.toneIndexByBank = {};
      for (var ix = 0; ix < a_tones.length; ix++) {
         var tone = a_tones[ix];

         var name = tone.Name;
         this.toneByName[name] = tone;

         // File has 1-based Program Number.  Lookup using UPG style 0-based.
         // Returns the INDEX of the Tone rather than the Tone itself
         var bank = tone.MSB + ':' + tone.LSB + ':' + (tone.PC - 1).toString();
         this.toneIndexByBank[bank] = ix;
      }
   }

   //--------------------------------------------------------------------------
   // Return an array containg integers BankMSB, BankLSB, (zero-based) PC the name for the specified name
   BankForName( a_name )
   {
      var tone =  this.toneByName[ a_name ];
      return [ parseInt(tone.MSB), parseInt(tone.LSB), parseInt(tone.PC) - 1 ];
   }

   //--------------------------------------------------------------------------
   // Return the name for the specified tone by index
   NameForIndex( a_index )
   {
      return this.toneArray[a_index].Name;
   }

   //--------------------------------------------------------------------------
   // Return the Tone index for the specified Bank and (zero-based) PC
   IndexForBank( a_bankMSB, a_bankLSB, a_PC )
   {
      var bank = a_bankMSB + ':' + a_bankLSB + ':' + a_PC;


      return this.toneIndexByBank[ bank ];
   }

   //--------------------------------------------------------------------------
   // Return an array containg BankMSB, BankLSB, and zero-based PC the name for the specified index
   BankForIndex( a_index )
   {
      var tone = this.toneArray[a_index];
      return [ parseInt(tone.MSB), parseInt(tone.LSB), parseInt(tone.PC) - 1 ];
   }

   //--------------------------------------------------------------------------
   // Fill a drop-list with the Tone names
   FillList( a_listID, a_showLocation = false, a_showCategory = false )
   {
      var toneList = document.getElementById( a_listID );
      while (toneList.firstChild) {
         toneList.removeChild(toneList.firstChild);
      }

      for (var ix=0; ix < this.toneArray.length; ix++) {
         var opt = document.createElement('option');
         opt.value = ix;
         var tone = this.toneArray[ix];

         // Longest name is 14 characters, padded with non-breaking spaces
         var str = tone.Name.padEnd(15,'\xA0');
         if (a_showLocation) {
            str += (' (' + tone.Location + ')').padEnd(14,'\xA0');
         }
         if (a_showCategory) {
            str += ' ' + tone.Category;
         }
         opt.innerHTML = str;
         toneList.appendChild(opt);
      }
   }
}

//--------------------------------------------------------------------------
// Fill a drop-list with Note names by MIDI note number
function FillNoteNameList( a_listID )
{
   var noteList = document.getElementById( a_listID );
   while (noteList.firstChild) {
      noteList.removeChild(noteList.firstChild);
   }

   var noteNames = [ 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B' ];
   var octave = -1;
   for (var ix=0; ix < 128; ix++) {
      var opt = document.createElement("option");
      opt.value = ix;
      var str = 'MIDI ' + ix + ': ' + noteNames[ ix % 12] + (octave + Math.floor(ix/12));
      switch (ix)
      {
      case 36:  str += ' low C'; break;
      case 60:  str += ' middle C'; break;
      case 84:  str += ' high C'; break;
      }

      opt.innerHTML = str;
      noteList.appendChild(opt);
   }
}

//-----------------------------------------------------------------------------
// Convert a_index into a Location string like "Piano 3"
function RegIndexAsLocation( a_index )
{
   return g_groupNames[ Math.floor(a_index/5) ] + ' ' + ((a_index % 5) + 1);
}

//-----------------------------------------------------------------------------
// Return an appropriate value for a_property from a_reg
function GetSafeRegProperty( a_reg, a_property )
{
   var retval = undefined;
   switch (a_property)
   {
   case 'comment':
      // Comment is a proprietary property not in Roland standard UPG
      retval = a_reg[ a_property ];
      if (retval) {
         // See the explanation in SetSafeRegProperty about why we segment this.
         let ix = 1;
         while (a_reg[ a_property + ix ]) {
            retval += a_reg[ a_property + ix ];
            ix += 1;
         }
      }
      else {
         retval = '';
      }
      break;

   case 'singleTone':
   case 'splitLowerTone':
   case 'dualTone2':
      // Read the appropriate sub-properties and convert to an index
      retval = g_toneList.IndexForBank( GetSafeRegProperty( a_reg, a_property + 'MSB' ),
                                        GetSafeRegProperty( a_reg, a_property + 'LSB' ),
                                        GetSafeRegProperty( a_reg, a_property + 'PC' ) );
      break;

   default:
      // Other properties must be present in the UPG
      // TODO: we COULD test for existance, and return default values, but it
      // isn't clear what the point might be, since "comment" is our only option.
      retval = a_reg[ a_property ];
      break;
   }

   return retval;
}

//-----------------------------------------------------------------------------
// Write an appropriate value for a_property to a_reg
function SetSafeRegProperty( a_reg, a_property, a_value )
{
   switch (a_property)
   {
   case 'comment':
      // Comment is a proprietary property not in Roland standard UPG.
      //
      // JSON would allow strings of arbitrary lengths.  But we don't know
      // the implementation of the FP-90, and don't want to risk giving it
      // a very long string which it isn't expecting.  So we limit the length
      // of each property and chop the string into multiple properties.
      let ix = 0;
      if (a_value) {
         let segMax = 64;
         let pos = 0;
         while (pos < a_value.length) {
            let chunk = a_value.substring( pos, pos+segMax );
            if (ix == 0) {
               a_reg[ a_property ] = chunk;
            }
            else {
               a_reg[ a_property + ix ] = chunk;
            }
            pos += chunk.length;
            ix += 1;
         }
      }
      else {
         // Writing an empty string removes the property, so it won't serialize
         delete a_reg[ a_property ];
         ix = 1;
      }

      // Delete any existing extension proprties that are not being used
      while (a_reg[ a_property + ix ]) {
         delete a_reg[ a_property + ix ];
         ix += 1;
      }
      break;

   case 'singleTone':
   case 'splitLowerTone':
   case 'dualTone2':
      // Convert the index into the appropriate sub-properties and save them
      bank = g_toneList.BankForIndex( a_value );
      a_reg[ a_property + 'MSB' ] = bank[0];
      a_reg[ a_property + 'LSB' ] = bank[1];
      a_reg[ a_property + 'PC' ]  = bank[2];
      break;

   default:
      // Other properties must be present in the UPG
      a_reg[ a_property ] = a_value;
      break;
   }
}

//-----------------------------------------------------------------------------
// Return an appropriate value from a_control
// <select> returns .selectedIndex as an integer
// <inputtype="checkbox"> returns .checked as 0 or 1
// <inputtype="number"> returns integer
// Other types return .value, generally a string
function GetControlValue( a_control )
{
   let retval = undefined;
   if (a_control.tagName == 'SELECT') {
      retval = a_control.selectedIndex;
   }
   else if ((a_control.tagName == 'INPUT') && (a_control.type == 'checkbox')) {
      retval = (a_control.checked) ? 1 : 0;
   }
   else if ((a_control.tagName == 'INPUT') && (a_control.type == 'number')) {
      retval = parseInt(a_control.value);
   }
   else {
      retval = a_control.value;
   }
   
   return retval;
}

//-----------------------------------------------------------------------------
// Set the value of a_control
// <select> set .selectedIndex, assumes a_value is an integer
// <inputtype="checkbox"> sets/clears .checked, assumes a_value is 1/0
// Other types set .value
function SetControlValue( a_control, a_value )
{
   if (a_control.tagName == 'SELECT') {
      a_control.selectedIndex = a_value;
   }
   else if ((a_control.tagName == 'INPUT') && (a_control.type == 'checkbox')) {
      a_control.checked = (a_value != 0);
   }
   else {
      a_control.value = a_value;
   }
}

//-----------------------------------------------------------------------------
// Simple help on fieldsets.
//
// COULD do context help: click a help button and then a label.
// Button sets a flag tested here to show help instead of normal click action.
// Need a way to make the Help button show its state.  An <input button> won't -
// it just moves the text somewhat.  Probably two images.
function onHelp( a_label )
{
   helpWindow = window.open( 'edit_help.html#' + a_label, "edit_help" );
   helpWindow.focus();
}
