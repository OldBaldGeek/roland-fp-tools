// edit_reg.js - JavaScript code to edit Registration (.UPG) files from
// Roland FP-60 and FP-90 pianos.
//
// Copyright (c) 2020-2023 by John Hartman

// Information about the current piano type
var g_pianoInfo = null;

// List of Tones read from the Tone file
var g_toneList = null;

// Name of the file from which we read the Registration data
var g_filename = '';

// Object with the Registration data
var g_upg = null;

// Currently selected row index, or -1 if none selected
var g_selectedRow = -1;

// Used to validate sessionData
const g_sessionDataCookie = 'Roland FP-60 Registration Data version 1.00';

// Change flag object
var g_changeFlag = null;

//-----------------------------------------------------------------------------
// Information selected by piano type
class PianoType
{
   constructor( a_name, a_def_regs_name, a_ideas_name, a_tone_list_name,
                a_reg_group_names, a_regs_per_group )
   {
      this.typeName       = a_name;
      this.def_regs_name  = a_def_regs_name;
      this.ideas_name     = a_ideas_name;
      this.tone_list_name = a_tone_list_name;
      this.reg_group_names = a_reg_group_names;
      this.regs_per_group  = a_regs_per_group;
   }
}

function SelectPiano( a_pianoType )
{
    // Names of the piano's Tone group buttons on the FP60 and FP90
    var groupNames = [ 'Piano', 'E.Piano', 'Strings', 'Organ', 'Pad', 'Other' ];

    // Names of the piano's Tone group buttons on the FP60X and FP90X
    var groupNamesX = [ 'Piano', 'E.Piano', 'Organ', 'String/Pad', 'Synth/Other' ];

    switch (a_pianoType) {
    case 'FP-60':
        g_pianoInfo = new PianoType( a_pianoType,                 // Type name
                                     'FP60_90_FACTORY_REGS.UPG',  // Factory reg file
                                     'FP60_90_IDEAS.UPG',         // Sample mods
                                     'Roland_FP60_90_tones.json', // Available tones
                                     groupNames,                  // Names of Reg. groups
                                     5 );                         // Regs per group
        break;
    case 'FP-90':
        g_pianoInfo = new PianoType( a_pianoType,
                                     'FP60_90_FACTORY_REGS.UPG',
                                     'FP60_90_IDEAS.UPG',
                                     'Roland_FP60_90_tones.json',
                                     groupNames,
                                     5 );
        break;
    case 'FP-60X':
        g_pianoInfo = new PianoType( a_pianoType,
                                     'FP60X_FACTORY_REGS.UPG',
                                     'FP60X_IDEAS.UPG',
                                     'Roland_FP60X_tones.json',
                                     groupNamesX,
                                     9 );
        break;
    case 'FP-90X':
        g_pianoInfo = new PianoType( a_pianoType,
                                     'FP90X_FACTORY_REGS.UPG',
                                     'FP90X_IDEAS.UPG',
                                     'Roland_FP90X_tones.json',
                                     groupNamesX,
                                     9 );
        break;
    default:
        alert('Unknown piano type ' + a_pianoType);
        return;
    }

    let pianoWas = sessionStorage.getItem('fp_pianoType');
    if (pianoWas != a_pianoType) {
        // Changing piano type: delete old session data
        sessionStorage.clear();
        sessionStorage.setItem( 'fp_pianoType', a_pianoType );
    }
}

//-----------------------------------------------------------------------------
class ItemInfo {
    constructor( a_name, a_default_value, a_pianos )
    {
        this.name = a_name;
        this.default_value = a_default_value;
        this.pianos = a_pianos;
    }

    // Return true if the item exists for a_piano
    hasItem( a_piano )
    {
        return this.pianos.indexOf(a_piano + ' ') >= 0;
    }
}

//-----------------------------------------------------------------------------
// Names Registration key names, most of which match editor controls.
// Drives the editor
var g_itemInfo = [
   new ItemInfo( "comment",         "",             "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "name",            "(none)",       "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "singleTone"    ,  "ConcertPiano", "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "splitLowerTone",  "Ac.Bass wRel", "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "dualTone2"     ,  "Strings forI", "FP-60 FP-90 FP-60X FP-90X " ),

   new ItemInfo( "keyboardMode",    0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "splitOctaveShift",0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "splitUpperOctaveShift", 0,        "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "splitPoint",      54,             "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "dualOctaveShift", 0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "dualTone1OctaveShift", 0,         "FP-60 FP-90 FP-60X FP-90X " ),

   new ItemInfo( "damperPedalPart", 0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "centerPedalPart", 0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "centerPedalFunc", 0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "leftPedalPart",   0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "leftPedalFunc",   0,              "FP-60 FP-90 FP-60X FP-90X " ),

   new ItemInfo( "rotarySpeed",     0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "modulationSpeed", 0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "upperVolume",     100,            "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "lowerVolume",     100,            "FP-60 FP-90 FP-60X FP-90X " ),

   new ItemInfo( "ambienceType",    2,              "                   FP-90X " ),
   new ItemInfo( "ambience",        2,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "keyTouch",        50,             "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "keyTransposeSw",  0,              "            FP-60X FP-90X " ),
   new ItemInfo( "keyTranspose",    0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "songTranspose",   0,              "FP-60 FP-90 FP-60X FP-90X " ),

   new ItemInfo( "midiTxCh",        1,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "registrationTxCh", 0,             "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "registrationBankMSB", 0,          "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "registrationBankLSB", 0,          "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "registrationPC",  0,              "FP-60 FP-90 FP-60X FP-90X " ),

   new ItemInfo( "micCompSw",       0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "micCompType",     1,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "micDoublingSw",   0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "micDoublingType", 0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "micDoublingWidth", 1,             "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "micDoublingLevel", 10,            "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "micEchoSw",       0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "micEchoType",     0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "micEchoLevel",    5,              "FP-60 FP-90 FP-60X FP-90X " ),

   new ItemInfo( "splitBalance",    0,              "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "dualBalance",     -5,             "FP-60 FP-90 FP-60X FP-90X " ),
   new ItemInfo( "twinPianoMode",   1,              "FP-60 FP-90 FP-60X FP-90X " )
];

//-----------------------------------------------------------------------------
// Make the Registration a_reg suitable for the current piano type:
// - if it is missing a property in the current piano, add the default value
// - if it has a property not in the current piano, delete the property
function refit_reg( a_reg )
{
    for (let ix = 0; ix < g_itemInfo.length; ix++)
    {
        let propID = g_itemInfo[ix].name;
        // GetSafeRegProperty will throw an error if any of
        // 'singleTone', 'splitLowerTone', 'dualTone2'
        // use a Tone that isn't valid on this piano
        try {
            let value = GetSafeRegProperty( a_reg, propID );
            if (g_itemInfo[ix].hasItem(g_pianoInfo.typeName)) {
                // Regs on this piano have this property
                if (value == null) {
                    // No value in local storage: use the default value
                    SetSafeRegProperty( a_reg, propID, g_itemInfo[ix].default_value );
                    console.log('Adding value for "' + propID + '": "' +
                                g_itemInfo[ix].default_value + '"');
                }
            }
            else {
                // Piano does not have this property
                if (value != null) {
                    // Delete  the incompatible value
                    delete a_reg[propID];
                    console.log('Deleting value for "' + propID + '"');
                }
            }
        }
        catch(e) {
            alert( '"' + propID + '" uses a Tone that this type of piano does not have.\n'
                    + e.toString() );
        }
    }
    
    return a_reg;
}

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
// Construct a tonelist, then invoke the callback
function MakeToneList( a_tone_list_name, a_completion_function )
{
    g_toneList = new ToneList();
    g_toneList.init( a_tone_list_name, a_completion_function );
}

//-----------------------------------------------------------------------------
// Class to deal with Tone list
class ToneList
{
    // Make an empty list
    constructor()
    {
        this.toneArray = [];
        this.toneByName = {};
        this.toneIndexByBank = {};
    }

    // Fill the list
    async init(a_tone_file, a_completion_function)
    {
        const response = await fetch(a_tone_file + '?' + (new Date()).getTime());
        this.toneArray = await response.json();

        // Create maps of the Tone list indexed by Name and Bank
        for (var ix = 0; ix < this.toneArray.length; ix++) {
            var tone = this.toneArray[ix];
            var name = tone.Name;
            this.toneByName[name] = tone;

            // File has 1-based Program Number.  Lookup using UPG style 0-based.
            // Returns the INDEX of the Tone rather than the Tone itself
            var bank = tone.MSB + ':' + tone.LSB + ':' + (tone.PC - 1).toString();
            this.toneIndexByBank[bank] = ix;
        }
        a_completion_function();
    }

   //--------------------------------------------------------------------------
   // Return an array containg integers [ BankMSB, BankLSB, (zero-based) PC ]
   // for the specified tone name
   BankForName( a_name )
   {
      var tone = this.toneByName[ a_name ];
      if (tone != null) {
        return [ parseInt(tone.MSB), parseInt(tone.LSB), parseInt(tone.PC) - 1 ];
      }
      
      alert( '"' + a_name + '" is not a known Tone for this piano.\n' );
      return [ 0, 68, 0 ];  // Acoustic piano as a default.
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
      let bank = a_bankMSB + ':' + a_bankLSB + ':' + a_PC;
      let retval = this.toneIndexByBank[ bank ];
      if (retval == null) {
         throw new Error('No Tone defined with MSBank=' + a_bankMSB +
                         ' LSBank='  + a_bankLSB +
                         ' Program=' + a_PC);
      }
      
      return retval;
   }

   //--------------------------------------------------------------------------
   // Return an array containg BankMSB, BankLSB, and zero-based PC the name for the specified index
   BankForIndex( a_index )
   {
      let tone = this.toneArray[a_index];
      return [ parseInt(tone.MSB), parseInt(tone.LSB), parseInt(tone.PC) - 1 ];
   }

   //--------------------------------------------------------------------------
   // Fill a drop-list with the Tone names
   FillList( a_listID, a_showLocation = false, a_showCategory = false )
   {
      let toneList = document.getElementById( a_listID );
      while (toneList.firstChild) {
         toneList.removeChild(toneList.firstChild);
      }

      for (let ix=0; ix < this.toneArray.length; ix++) {
         let opt = document.createElement('option');
         opt.value = ix;
         let tone = this.toneArray[ix];

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
   let group = Math.floor(a_index/g_pianoInfo.regs_per_group);
   let ix = a_index % g_pianoInfo.regs_per_group;
   return g_pianoInfo.reg_group_names[group] + ' ' + (ix + 1);
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
      // TODO: we COULD test for existence, and return default values, but it
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
