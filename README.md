jack_mixer -- Jack Audio Mixer
==============================

**jack_mixer** is a GTK+ JACK audio mixer app with a look & handling similar to
hardware mixing desks. It has lot of useful features, apart from being able to
mix multiple JACK audio streams.

It is licensed under GPL version 2 (or later), check the file [COPYING] for
more information.

Please visit the project's homepage at https://rdio.space/jackmixer/ for more
information.


## Installation

To build and install jack_mixer one would typically run:

```console
./autogen.sh --prefix=/usr
make
sudo make install
```

Please read the file [INSTALL] for more information.


## Using MIDI CCs to control jack_mixer

MIDI Control Change messages (CCs) can be used to control volume,
balance/panorama, mute, and solo of input and output channels.

The default controllers for added channels are chosen using a predefined
algorithm: the first free controller starting from #11, first for volume, next
for balance/panorama, then mute and finally solo.

So, if you don't delete channels, CC#11 will control the first channel's
volume, CC#12 the balance/panorama, CC#13 the mute and CC#14 the solo switch.
CC#15 will control the second channel' volume, CC#16 it's balance/panorama, and
so on.

It is also possible to set other CCs when creating a channel, or afterwards
from the channel properties dialog (accessible from the menu or by double
clicking on the channel name).

MIDI CC values (0-127) are mapped to dBFS using the current slider scale for
the corresponding channel.


## Feedback

If you have trouble getting jack_mixer working, find a bug or you miss some
feature, please [create an issue] on GitHub or contact the maintainer by email.

jack_mixer was initially written and supported by Nedko Arnaudov, it is now
maintained by Frédéric Péters. You can reach Frédéric at fpeters (a.t) 0d (dot)
be, and Nedko at nedko (a.t) arnaudov (dot) name. Most recently, the primary
developers are Daniel Sheeler at dsheeler (a.t) pobox (dot) com and Christopher
Arndt at chris (a.t) chrisarndt (dot) de, and you can also usually find these
folks in #jack_mixer or #lad on FreeNode (as fpeters, nedko, dsheeler and
strogon14).


## Acknowledgements

K-meter implemenatation taken from jkmeter, licensed under
the GPL 2, by Fons Adriaensen.

[COPYING]: ./COPYING
[INSTALL]: ./INSTALL
[create an issue]: https://github.com/jack-mixer/jack_mixer/issues
