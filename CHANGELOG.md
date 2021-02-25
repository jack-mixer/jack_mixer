Change Log
==========


## Version 14 (2020-10-15)

* Changes to channel fader/meter layout and features:
    * Added K20 and K14 scales.
    * Added tick marks for left/center/right on balance slider and add tooltip
      displaying left/right value.
    * Added maximum width for control group labels. Labels are ellipsized if
      too long and a tooltip with the full name is added.
* Channel add/property dialogs usability improvements:
    * Remember last used settings for new input/outut channel dialogs (MIDI CCs
      are always initialized with -1 by default, so they can be auto-assigned).
    * Channel name is pre-filled in with "Input" or "output" and an
      auto-incremented number suffix.
    * Add mnemonics for all input/output channel dialog fields.
* When running under NSM, closing the main window only hides UI and the "Quit"
  menu entry is replaced with a "Hide" entry.
* Added a global option to always ask for confirmation when quitting
  jack_mixer.
* Allow drag'n'drop to change channel positions.
* Added ability to shrink/expand width of input and output channels.
* The font color of control group labels automatically adapts to their
  background color for better contrast and readability.
* Fixed: Ctrl-click on volume fader sets it to 0.0 dbFS, not 1.0.
* Fixed: some issues with channel monitoring.
* Fixed: don't create empty project file on new NSM session.
* Fixed: on project load, give input focus to fader of last added channel and
  deselect volume entry widget so keyboard input doesn't accidentally change
  the value.

With contributions from Christopher Arndt, Daniel Sheeler and Frédéric Péters.


## Version 13 (2020-07-16)

* Added NSM support.
* Store preferences to per session config file to override global
  preferences.
* Added accelerator shortcuts to menu items.
* New ctrl-click, double-click, scroll, and click-drag-anywhere
  fader behaviors.
* Added MIDI 'Pick Up' behavior to avoid discontinuities.
* Can choose output channel colors.
* Changed to logarithmic ramping on volume changes.
* Added a pre/post fader button.
* Pick volume for new channels.
* Allow manual setting of MIDI control change numbers.
* Remove GConf; use plaintext .ini preferences file instead.
* Remove remnants of Swig python bindings.

With contributions from Daniel Sheeler and Christopher Arndt.


## Version 12 (2020-06-22)

* Added reporting of the current volume through SIGUSR1 signal to
  jack_mix_box.
* Reset color of over 0db/NaN peak on click.
* Fixed memory leaks.
* Fixed some Python 3 compatibility leftovers.

With contributions from Daniel Sheeler and Athanasios Silis.


## Version 11 (2020-06-18)

* Spread out volume transition over a period of time to reduce
  discontinuities.
* Port to pygobject and GTK3.
* Port to Python 3.

With contributions from Daniel Sheeler.


## Version 10 (2014-04-27)

* Fixed change of channel settings (#18299)
* Added a MIDI out port for feeding back volume levels into motorized
  controllers
* Added jack_mix_box, a minimalistic (no UI) jack mixer
* Added a trayicon and minimize to tray feature

With contributions from John Hedges, Sarah Mischke, and Nedko Arnaudov.


## Version 9 (2010-10-04)

* Changed to no longer appends PID to jack client name (#15006)
* Added 'Edit .. channel' submenus
* Set a default 'apply' button in channel properties
* Fixed creation of  mono channels
* Removed bad crackling when changing the volume through MIDI
* Moved back to polling for MIDI events, to avoid the need for threads
* Changed to use backward compatible call to gobject.timeout_add (#14999)
* Updated not to fail if we can't get lash server name
* Added support for Ladish level 1
* Improved SIGUSR1 handling

With contributions from Nedko Arnaudov and Arnout Engelen.


## Version 8 (2009-12-16)

* Fix private modules lookup
* Fix rotation of output channel colours
* New menu items to remove output channels
* New command line parameter to not connect to LASH


## Version 7 (2009-12-14)

* New maintainer, thanks Nedko for everything!
* New icon by Lapo Calamandrei
* Option to have a gradient in the vumeters
* Option to use stock GtkScale widget for volume and balance
* Rewrite of the C/Python binding (this removed the dependency on SWIG)
* Improve performance when drawing vumeters
* New menu items to load/save settings
* New "Channel Properties" dialog, allowing to change assigned MIDI CCs
* Automatic post fader outputs for input channels
* Possibility to add new output channels, besides main mix
* New "monitor" output, assignable to any output channel, or input channel
  (in which case it will take its prefader volume)
* Removal of PyXML dependency

With contributions from Nedko Arnaudov, Lapo Calamandrei, Arnout Engelen,
and Krzysztof Foltman.


## Version 6 (2009-07-25)

* Fix building against jack 0.102.20
* Handle python prefix different from install prefix
* Fix LASH-less operation
* Update install instructions after lash-0.5.3 and phat-0.4.1 releases
* Apply Markus patch (thanks!) for sr #1698 (can't restore session using LASH)
