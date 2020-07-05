#
# _jack_mixer.pyx
#

__all__ = ("Scale", "Mixer")

import enum

from _jack_mixer cimport *


cdef void midi_change_callback_func(void *userdata) with gil:
    """Wrapper for a Python callback function for MIDI input."""
    channel = <object> userdata
    channel._midi_change_callback()


class MidiBehaviour(enum.IntEnum):
    JUMP_TO_VALUE = 0
    PICK_UP = 1


cdef class Scale:
    cdef jack_mixer_scale_t _scale

    def __cinit__(self):
        self._scale = scale_create()

    def __dealloc__(self):
        if self._scale:
            scale_destroy(self._scale)

    cpdef bool add_threshold(self, float db, float scale_value):
        return scale_add_threshold(self._scale, db, scale_value)

    cpdef void remove_thresholds(self):
        scale_remove_thresholds(self._scale)

    cpdef void calculate_coefficients(self):
        scale_calculate_coefficients(self._scale)

    cpdef double db_to_scale(self, double db):
        return scale_db_to_scale(self._scale, db)

    cpdef double scale_to_db(self, double scale_value):
        return scale_scale_to_db(self._scale, scale_value)


cdef class Mixer:
    cdef jack_mixer_t _mixer
    cdef bool _stereo

    def __cinit__(self, name, stereo=True):
        self._stereo = stereo
        self._mixer = mixer_create(name.encode('utf-8'), stereo)

    def __dealloc__(self):
        if self._mixer:
            mixer_destroy(self._mixer)

    def destroy(self):
        if self._mixer:
            mixer_destroy(self._mixer)

    @property
    def channels_count(self):
        return mixer_get_channels_count(self._mixer)

    @property
    def client_name(self):
        return mixer_get_client_name(self._mixer).decode('utf-8')

    @property
    def last_midi_channel(self):
        return mixer_get_last_midi_channel(self._mixer)

    @last_midi_channel.setter
    def last_midi_channel(self, int channel):
        mixer_set_last_midi_channel(self._mixer, channel)

    @property
    def midi_behavior_mode(self):
        return MidiBehaviour(mixer_get_midi_behavior_mode(self._mixer))

    @midi_behavior_mode.setter
    def midi_behavior_mode(self, mode):
        mixer_set_midi_behavior_mode(self._mixer,
                                     mode.value if isinstance(mode, MidiBehaviour) else mode)

    cpdef add_channel(self, channel_name, stereo=None):
        if stereo is None:
            stereo = self._stereo

        return Channel.new(mixer_add_channel(self._mixer, channel_name.encode('utf-8'), stereo))

    cpdef add_output_channel(self, channel_name, stereo=None, system=False):
        if stereo is None:
            stereo = self._stereo

        return OutputChannel.new(mixer_add_output_channel(self._mixer,
                                                          channel_name.encode('utf-8'),
                                                          stereo, system))


cdef class Channel:
    cdef jack_mixer_channel_t _channel
    cdef object _midi_change_callback

    def __init__(self):
        raise TypeError("Channel instances can only be created via Mixer.add_channel().")

    @staticmethod
    cdef Channel new(jack_mixer_channel_t chan_ptr):
        print("Channel.new")
        cdef Channel channel = Channel.__new__(Channel)
        channel._channel = chan_ptr
        return channel

    @property
    def abspeak(self):
        if self._channel:
            return channel_abspeak_read(self._channel)

    @abspeak.setter
    def abspeak(self, reset):
        if self._channel:
            if reset is not None:
                raise ValueError("abspeak can only be reset (set to None)")
            channel_abspeak_reset(self._channel)

    @property
    def balance(self):
        if self._channel:
            return channel_balance_read(self._channel)

    @balance.setter
    def balance(self, double bal):
        if self._channel:
            channel_balance_write(self._channel, bal)

    @property
    def is_stereo(self):
        if self._channel:
            return channel_is_stereo(self._channel)

    @property
    def meter(self):
        cdef double left, right

        if self._channel:
            if channel_is_stereo(self._channel):
                channel_stereo_meter_read(self._channel, &left, &right)
                return (left, right)
            else:
                channel_mono_meter_read(self._channel, &left)
                return (left,)

    @property
    def midi_change_callback(self):
        if self._channel:
            return self._midi_change_callback

    @midi_change_callback.setter
    def midi_change_callback(self, callback):
        if self._channel:
            self._midi_change_callback = callback
            if callback is None:
                channel_set_midi_change_callback(self._channel, NULL, NULL)
            else:
                channel_set_midi_change_callback(self._channel,
                                                 &midi_change_callback_func,
                                                 <void *>self)

    @property
    def name(self):
        if self._channel:
            return channel_get_name(self._channel).decode('utf-8')

    @name.setter
    def name(self, newname):
        if self._channel:
            channel_rename(self._channel, newname.encode('utf-8'))

    @property
    def out_mute(self):
        if self._channel:
            return channel_is_out_muted(self._channel)

    @out_mute.setter
    def out_mute(self, bool value):
        if self._channel:
            if value:
                channel_out_mute(self._channel)
            else:
                channel_out_unmute(self._channel)

    @property
    def solo(self):
        if self._channel:
            return channel_is_soloed(self._channel)

    @solo.setter
    def solo(self, bool value):
        if self._channel:
            if value:
                channel_solo(self._channel)
            else:
                channel_unsolo(self._channel)

    @property
    def midi_in_got_events(self):
        if self._channel:
            return channel_get_midi_in_got_events(self._channel)

    @property
    def midi_scale(self):
        raise AttributeError("midi_scale can only be set.")

    @midi_scale.setter
    def midi_scale(self, Scale scale):
        if self._channel:
            channel_set_midi_scale(self._channel, scale._scale)

    @property
    def volume(self):
        if self._channel:
            return channel_volume_read(self._channel)

    @volume.setter
    def volume(self, double vol):
        if self._channel:
            channel_volume_write(self._channel, vol)

    @property
    def balance_midi_cc(self):
        if self._channel:
            return channel_get_balance_midi_cc(self._channel)

    @balance_midi_cc.setter
    def balance_midi_cc(self, int cc):
        if self._channel:
            channel_set_balance_midi_cc(self._channel, cc)

    @property
    def mute_midi_cc(self):
        if self._channel:
            return channel_get_mute_midi_cc(self._channel)

    @mute_midi_cc.setter
    def mute_midi_cc(self, int cc):
        if self._channel:
            channel_set_mute_midi_cc(self._channel, cc)

    @property
    def solo_midi_cc(self):
        if self._channel:
            return channel_get_solo_midi_cc(self._channel)

    @solo_midi_cc.setter
    def solo_midi_cc(self, int cc):
        if self._channel:
            channel_set_solo_midi_cc(self._channel, cc)

    @property
    def volume_midi_cc(self):
        if self._channel:
            return channel_get_volume_midi_cc(self._channel)

    @volume_midi_cc.setter
    def volume_midi_cc(self, int cc):
        if self._channel:
            channel_set_volume_midi_cc(self._channel, cc)

    def autoset_balance_midi_cc(self):
        if self._channel:
            channel_autoset_balance_midi_cc(self._channel)

    def autoset_mute_midi_cc(self):
        if self._channel:
            channel_autoset_mute_midi_cc(self._channel)

    def autoset_solo_midi_cc(self):
        if self._channel:
            channel_autoset_solo_midi_cc(self._channel)

    def autoset_volume_midi_cc(self):
        if self._channel:
            channel_autoset_volume_midi_cc(self._channel)

    def remove(self):
        if self._channel:
            remove_channel(self._channel)


cdef class OutputChannel(Channel):
    cdef jack_mixer_output_channel_t _output_channel

    def __init__(self):
        raise TypeError("OutputChannel instances can only be created via "
                        "Mixer.add_output_channel().")

    @staticmethod
    cdef OutputChannel new(jack_mixer_output_channel_t chan_ptr):
        cdef OutputChannel channel = OutputChannel.__new__(OutputChannel)
        channel._output_channel = chan_ptr
        channel._channel = <jack_mixer_channel_t> chan_ptr
        return channel

    def is_muted(self, Channel channel):
        if self._output_channel:
            return output_channel_is_muted(self._output_channel, channel._channel)

    def set_muted(self, Channel channel, bool value):
        if self._output_channel:
            output_channel_set_muted(self._output_channel, channel._channel, value)

    def is_prefader(self):
        if self._output_channel:
            return output_channel_is_prefader(self._output_channel)

    def set_prefader(self, bool value):
        if self._output_channel:
            output_channel_set_prefader(self._output_channel, value)

    def is_solo(self, Channel channel):
        if self._output_channel:
            return output_channel_is_solo(self._output_channel, channel._channel)

    def set_in_prefader(self, Channel channel, bool value):
        if self._output_channel:
            output_channel_set_in_prefader(self._output_channel, channel._channel, value)

    def set_solo(self, Channel channel, bool value):
        if self._output_channel:
            output_channel_set_solo(self._output_channel, channel._channel, value)

    def remove(self):
        if self._output_channel:
            remove_output_channel(self._output_channel)
