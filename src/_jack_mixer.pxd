#
# _jack_mixer.pxd
#
# cython: language_level=3
#

from libcpp cimport bool

cdef extern from "jack_mixer.h":
    # scale.h
    ctypedef void * jack_mixer_scale_t;

    cdef jack_mixer_scale_t scale_create()

    cdef bool scale_add_threshold(jack_mixer_scale_t scale, float db, float scale_value)
    cdef void scale_remove_thresholds(jack_mixer_scale_t scale)
    cdef void scale_calculate_coefficients(jack_mixer_scale_t scale)
    cdef double scale_db_to_scale(jack_mixer_scale_t scale, double db)
    cdef double scale_scale_to_db(jack_mixer_scale_t scale, double scale_value)
    cdef void scale_destroy(jack_mixer_scale_t scale)

    # jack_mixer.h
    ctypedef void * jack_mixer_t
    ctypedef void * jack_mixer_channel_t
    ctypedef void * jack_mixer_output_channel_t
    ctypedef void * jack_mixer_threshold_t

    ctypedef void (*midi_change_callback)(void *) noexcept with gil

    cdef enum midi_behavior_mode:
        pass

    cdef enum meter_mode:
        pass

    ctypedef enum jack_mixer_error_t:
        pass

    cdef jack_mixer_error_t jack_mixer_error();

    cdef const char* jack_mixer_error_str();

    # mixer
    cdef jack_mixer_t mixer_create "create" (const char * jack_client_name_ptr, bool stereo)
    cdef void mixer_destroy "destroy" (jack_mixer_t mixer)
    cdef unsigned int mixer_get_channels_count "get_channels_count" (jack_mixer_t mixer)
    cdef const char * mixer_get_client_name "get_client_name" (jack_mixer_t mixer)
    cdef int mixer_get_last_midi_cc "get_last_midi_cc" (jack_mixer_t mixer)
    cdef void mixer_set_last_midi_cc "set_last_midi_cc" (
        jack_mixer_t mixer,
        int new_channel)
    cdef int mixer_get_midi_behavior_mode "get_midi_behavior_mode" (jack_mixer_t mixer)
    cdef void mixer_set_midi_behavior_mode "set_midi_behavior_mode" (
        jack_mixer_t mixer,
        midi_behavior_mode mode)
    cdef jack_mixer_channel_t mixer_add_channel "add_channel" (
        jack_mixer_t mixer,
        const char * channel_name,
        bool stereo)
    cdef jack_mixer_output_channel_t mixer_add_output_channel "add_output_channel" (
        jack_mixer_t mixer,
        const char * channel_name,
        bool stereo,
        bool system)
    cdef bool mixer_get_kmetering "get_kmetering" (jack_mixer_t mixer)
    cdef void mixer_set_kmetering "set_kmetering" (jack_mixer_t mixer, bool flag)

    # not used by Python
    #cdef void channels_volumes_read(jack_mixer_t mixer)
    #cdef void remove_channels(jack_mixer_t mixer)

    # channel
    cdef const char * channel_get_name(jack_mixer_channel_t channel)
    cdef int channel_rename(jack_mixer_channel_t channel, const char * name)

    cdef double channel_abspeak_read(jack_mixer_channel_t channel, meter_mode mode)
    cdef void channel_abspeak_reset(jack_mixer_channel_t channel, meter_mode mode)

    cdef void channel_mono_meter_read(
        jack_mixer_channel_t channel,
        double * mono_ptr,
        meter_mode mode)
    cdef void channel_stereo_meter_read(
        jack_mixer_channel_t channel,
        double * left_ptr,
        double * right_ptr,
        meter_mode mode)

    cdef void channel_mono_kmeter_read(
        jack_mixer_channel_t channel,
        double * left_ptr,
        double * left_rms_ptr,
        meter_mode mode)
    cdef void channel_stereo_kmeter_read(
        jack_mixer_channel_t channel,
        double * left_ptr,
        double * right_ptr,
        double * left_rms_ptr,
        double * right_rms_ptr,
        meter_mode mode)

    cdef void channel_mono_kmeter_reset(jack_mixer_channel_t channel)
    cdef void channel_stereo_kmeter_reset(jack_mixer_channel_t channel)

    cdef void channel_volume_write(jack_mixer_channel_t channel, double volume)
    cdef double channel_volume_read(jack_mixer_channel_t channel)

    cdef double channel_balance_read(jack_mixer_channel_t channel)
    cdef void channel_balance_write(jack_mixer_channel_t channel, double balance)

    cdef bool channel_is_out_muted(jack_mixer_channel_t channel)
    cdef void channel_out_mute(jack_mixer_channel_t channel)
    cdef void channel_out_unmute(jack_mixer_channel_t channel)

    cdef bool channel_is_soloed(jack_mixer_channel_t channel)
    cdef void channel_solo(jack_mixer_channel_t channel)
    cdef void channel_unsolo(jack_mixer_channel_t channel)

    cdef bool channel_is_stereo(jack_mixer_channel_t channel)

    cdef void channel_set_midi_change_callback(
        jack_mixer_channel_t channel,
        midi_change_callback callback,
        void * user_data)
    cdef bool channel_get_midi_in_got_events(jack_mixer_channel_t channel)

    cdef int channel_autoset_balance_midi_cc(jack_mixer_channel_t channel)
    cdef int channel_autoset_mute_midi_cc(jack_mixer_channel_t channel)
    cdef int channel_autoset_solo_midi_cc(jack_mixer_channel_t channel)
    cdef int channel_autoset_volume_midi_cc(jack_mixer_channel_t channel)

    cdef int channel_get_balance_midi_cc(jack_mixer_channel_t channel)
    cdef int channel_get_mute_midi_cc(jack_mixer_channel_t channel)
    cdef int channel_get_solo_midi_cc(jack_mixer_channel_t channel)
    cdef int channel_get_volume_midi_cc(jack_mixer_channel_t channel)
    cdef int channel_set_balance_midi_cc(jack_mixer_channel_t channel, int new_cc)
    cdef int channel_set_mute_midi_cc(jack_mixer_channel_t channel, int new_cc)
    cdef int channel_set_solo_midi_cc(jack_mixer_channel_t channel, int new_cc)
    cdef int channel_set_volume_midi_cc(jack_mixer_channel_t channel, int new_cc)

    cdef void channel_set_midi_scale(jack_mixer_channel_t channel, jack_mixer_scale_t scale)

    cdef void channel_set_midi_cc_balance_picked_up(jack_mixer_channel_t channel, bool status)
    cdef void channel_set_midi_cc_volume_picked_up(jack_mixer_channel_t channel, bool status)

    cdef void remove_channel(jack_mixer_channel_t channel)

    # output channel
    cdef bool output_channel_is_muted(
        jack_mixer_output_channel_t output_channel,
        jack_mixer_channel_t channel)
    cdef void output_channel_set_muted(
        jack_mixer_output_channel_t output_channel,
        jack_mixer_channel_t channel,
        bool muted_value)
    cdef bool output_channel_is_prefader(
        jack_mixer_output_channel_t output_channel)
    cdef void output_channel_set_prefader(
        jack_mixer_output_channel_t output_channel,
        bool pfl_value)
    cdef bool output_channel_is_in_prefader(
        jack_mixer_output_channel_t output_channel,
        jack_mixer_channel_t input_channel)
    cdef void output_channel_set_in_prefader(
        jack_mixer_output_channel_t output_channel,
        jack_mixer_channel_t input_channel,
        bool prefader_value)
    cdef bool output_channel_is_solo(
        jack_mixer_output_channel_t output_channel,
        jack_mixer_channel_t channel)
    cdef void output_channel_set_solo(
        jack_mixer_output_channel_t output_channel,
        jack_mixer_channel_t channel,
        bool solo_value)
    cdef void remove_output_channel(jack_mixer_output_channel_t output_channel)
