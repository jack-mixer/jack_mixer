Change Log
==========

## Version 18 (2023-11-09)

Fixed:

* Compilation with Cython >= 3 has been fixed (#176).
* Output channel name changes are properly reflected in input channel control
  groups (#177).
* Prefader kmeters now also fall at same rate regardless of jack buffer size.
* The Spanish translations was updated (#168).

Changes:

* `PyXDG` has been replaced with `appdirs` (#150).
* `mesonep517` has been replaced with `meson-python` for PEP-517 compliant
  builds (for testing needs only) (#179).
* All log messages are now prefixed with `[jack_mixer]` so they can be better
  recognized / filtered in the NSM session logs (#162).
* The included `nsmclient` module was updated (#164).

Features:

* NSM implementation now includes support for dirty/clean save status (#154).

With contributions from Christopher Arndt, Daryl Hanlon, Nils Hilbricht, Mark
Knoop and Daniel Sheeler.


## Version 17 (2021-10-15)

Fixed:

* Uniform fall rate for kmeter peak indicators across different jack
  buffer sizes was enforced (#133).

Features:

* Install a Ray Session template file that tells Ray Session this
  version has nsm support (#131).
* A Spanish translation was added.
* Ability to reset absolute peak meter readings after a user chosen
  time was added (#135).
* Custom slider mouse behavior was changed to mimic that of gtk slider,
  in particular, the fader no longer jumps to click position but requires
  a click and drag to move it (#137).
* Minimum and maximum width for custom sliders was added.
* Minimum and maximum width for meters was added.
* Meter redraw period as a user preference was added (#139).
* Ability to meter pre-fader signal was added (#97).
* Keypad plus and minus accelerator for channel shrink/expand (#141)

With contributions from Daniel Sheeler and Christopher Arndt and with
Daryl Hanlon providing the Spanish translation.


## Version 16 (2021-04-15)

Fixed:

* Some global settings were not properly persisted in the settings file
  when changed in the preferences dialog (#124).
* Selecting a custom default project path in the preferences dialog via
  folder selection widget did not update the path in the text entry.
* The message formatting in error dialogs was corrected and when an error
  dialog is shown, the error message printed to the console now only
  contains a Python traceback when the debug option is active.
* Various debug log messages received minor fixes and improvements.

Features:

* Internationalization (i18n) support was added, making GUI labels and
  messages and the command line help translatable.
* A German translation was added.
* A French translation was added.
* A global language setting was added to the preferences.
* French and German translations of the application description were added to
  the XDG desktop file.

Documentation:

* A man page for `jack_mix_box` was added.
* A new [contributing guide](./docs/CONTRIBUTING.md) was added to repository.
* The section on environment variables in `jack_mixer's` man page was updated
  and enhanced.
* The NSM project URL was updated in various documents.

This release was created by Christopher Arndt with Olivier Humbert providing
the French translation.


## Version 15.1 (2021-03-15)

**Bugfix release**

Fixed:

* In fixing issue #81 a regression was introduced in version 15, which caused
  channel volume levels to not be restored when loading a project XML file.

* The `Channel.autoset_*_midi_cc` methods in the Cython extension module didn't
  return the int result from the C functions they call, causing mis-leading
  debug log messages.


Project infrastructure and internals:

* A [wiki] was added to the `jack_mixer` GitHub project and a page with
  instructions on how to install from source on debian / Ubuntu.

* The dependencies for building a Python wheel via `pip` were updated.

* When building from a Git checkout, the `cython` program is also found when it
  is installed as `cython3`.

* Debug logging can be enabled by setting the `JACK_MIXER_DEBUG` environment
  variable (for when the `-d` command line switch can't be used, e.g. when run
  via NSM).

This release was created by Christopher Arndt.


[wiki]: https://github.com/jack-mixer/jack_mixer/wiki


## Version 15 (2021-02-25)

**Important change:** `jack_mixer` now uses [meson] for building and
installation. See [INSTALL.md] for new build instructions.


New:

* A global setting for default project file path was added and can be changed
  in the preference dialog.

    The default value is `$XDG_DATA_HOME/jack_mixer` (which is normally
    `~/.local/share/jack_mixer`).

* A "Recent projects" menu was added, to allow loading recently used / saved
  projects more quickly.

* Direct channel output ports are now optional and can be enabled/disabled in
  the channel preferences dialog.

* Ctrl+left-click on the mute ("M") or solo ("S") channel buttons now activates
  exclusive mute resp. solo.

* A man page for `jack_mixer` was added.

* `jack_mix_box` now supports the `-p|--pickup` command line option to enable
  MIDI pickup mode, to prevent sudden volume or balance value jumps.


Fixed:

* Activating the solo function on an input channel could cause its
  output signal be sent to the monitor outputs instead of the signal
  from the channel, which had monitoring activated.

* Volume and balance level and mute and solo state changes originating from
  the UI now send the correct assigned MIDI CCs, allowing for MIDI feedback
  to controllers. Same for changes originating from reception of assigned MIDI
  CCs.

* The handler for right-clicking the input channel mute/solo buttons, was
  accidentally removed and is now re-instated.

* Creating a new output channel assigns it a randomly chosen color,
  which can be changed in the new channel dialog (used to work
  some releases ago, but was broken at some point).

* The `jack_mix_box` command line options `--help` and `--stereo`
  erroneously required an argument.

* Saving the current project on reception of the `SIGUSR1` signal, which is a
  requirement for LADISH level L1 support, was broken in version 14.

* When re-ordering channels via drag-and-drop, the order of the edit / remove
  channel menu items were not updated.

* When creating an output channel, it could happen that the initial channel
  volume would randomly be set to -inf or 0 dB, regardless of what was
  selected in new channel dialog.


Changed:

* The minimum supported Python version is now 3.6.

* The `jack_mix_box` command line usage help message was improved.

* The channel strip buttons (solo, mute, etc.) now have more distinctive colors
  when activated or the mouse hovers over them.

* The balance slider step size was increased slightly so right-clicking the
  slider changes the value more rapidly.

* When using the "Save as..." function, `jack_mixer` now sets the default
  filename and directory for file chooser to the last ones used.

* A window title was added to the preferences dialog.

* MIDI control for mute and solo now interprets control value 0-63 as off
  and 64-127 as on, instead of toggling the state on reception of any
  controller value.


Project infrastructure and internals:

* The `jack_mixer_c` Python extension module, which was originally implemented
  in hand-written C code using the PYTHON C API, was replaced with the
  `_jack_mixer` extension module implemented in [Cython], which generates the C
  code in `_jack_mixer.c`.

* The autotools build toolchain was replaced with a build setup using [meson],
  which improves build times and maintainability markedly. See the file
  [INSTALL.md] for updated build and installation instructions.

* A build option to allow building only `jack_mix_box` was added (`-Dgui=disabled`).

* All Python code was re-formatted with [black].

* All errors and warnings reported by [flake8] were fixed or are explicitly and
  selectively ignored.

* The file `version.py` is now generated from the version set in the project
  definition in the top-level `meson.build` file, leaving this as the only
  place where the version number needs to be updated before a release.

* The `NEWS` file was renamed to `CHANGELOG.md` and converted to Markdown
  format.

This release was created by Christopher Arndt. With a contribution from
Athanasios Silis.


[INSTALL.md]: ./INSTALL.md
[black]: https://pypi.org/project/black/
[Cython]: https://cython.org/
[meson]: https://mesonbuild.com/
[flake8]:  https://pypi.org/project/flake8/


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
