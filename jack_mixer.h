/* -*- Mode: C ; c-basic-offset: 2 -*- */
/*****************************************************************************
 *
 *   This file is part of jack_mixer
 *
 *   Copyright (C) 2006 Nedko Arnaudov <nedko@arnaudov.name>
 *
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published by
 *   the Free Software Foundation; version 2 of the License
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with this program; if not, write to the Free Software
 *   Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 *****************************************************************************/

#ifndef JACK_MIXER_H__DAEB51D8_5861_40F2_92E4_24CA495A384D__INCLUDED
#define JACK_MIXER_H__DAEB51D8_5861_40F2_92E4_24CA495A384D__INCLUDED

#ifdef SWIG
%module jack_mixer_c
%include "typemaps.i"
%apply double *OUTPUT { double * left_ptr, double * right_ptr, double * mono_ptr };
%{
#include <stdbool.h>
#include "jack_mixer.h"
%}
#endif
#include <jack/jack.h>
#include <stdbool.h>
#include <glib.h>

#include "scale.h"

typedef void * jack_mixer_t;
typedef void * jack_mixer_channel_t;
typedef void * jack_mixer_output_channel_t;
typedef void * jack_mixer_threshold_t;
typedef void * jack_mixer_frames_t;

enum midi_behavior_mode { Jump_To_Value, Pick_Up };

struct volume
{
  float value;
  unsigned int idx;
  float value_new;
};

struct frames
{
  jack_default_audio_sample_t *left;
  jack_default_audio_sample_t *right;
};

struct channel
{
  struct jack_mixer * mixer_ptr;
  char * name;
  bool stereo;
  bool out_mute;
  float volume_transition_seconds;
  unsigned int num_volume_transition_steps;
  /*float volume;
  jack_nframes_t volume_idx;
  float volume_new;*/
  struct volume *volume;
  GData *send_volumes;
  char current_send[64];
  float balance;
  jack_nframes_t balance_idx;
  float balance_new;
  /*GData *volumes_left;
  GData *volumes_left_new;
  GData *volumes_right;
  GData *volumes_right_new;*/
  float volume_initial;
  float volume_left;
  float volume_left_new;
  float volume_right;
  float volume_right_new;
  float meter_left;
  float meter_right;
  float abspeak;
  jack_port_t * port_left;
  jack_port_t * port_right;

  jack_nframes_t peak_frames;
  float peak_left;
  float peak_right;

  GData *frames;
  jack_default_audio_sample_t * tmp_mixed_frames_left;
  jack_default_audio_sample_t * tmp_mixed_frames_right;

  jack_default_audio_sample_t * prefader_frames_left;
  jack_default_audio_sample_t * prefader_frames_right;

  bool NaN_detected;

  int midi_cc_volume_index;
  int midi_cc_balance_index;
  int midi_cc_mute_index;
  int midi_cc_solo_index;
  bool midi_cc_volume_picked_up;
  bool midi_cc_balance_picked_up;

  jack_default_audio_sample_t * left_buffer_ptr;
  jack_default_audio_sample_t * right_buffer_ptr;

  bool midi_in_got_events;
  void (*midi_change_callback) (void*);
  void *midi_change_callback_data;
  bool midi_out_has_events;

  jack_mixer_scale_t midi_scale;
};

struct output_channel {
  struct channel channel;
  GSList *soloed_channels;
  GSList *muted_channels;
  GSList *prefader_channels;
  /*jack_default_audio_sample_t * frames_left;
  jack_default_audio_sample_t * frames_right;*/
  bool system; /* system channel, without any associated UI */
  bool prefader;
};

struct jack_mixer
{
  pthread_mutex_t mutex;
  jack_client_t * jack_client;
  GSList *input_channels_list;
  GSList *output_channels_list;
  GSList *soloed_channels;

  jack_port_t * port_midi_in;
  jack_port_t * port_midi_out;
  int last_midi_channel;
  enum midi_behavior_mode midi_behavior;

  struct channel* midi_cc_map[128];
};
jack_mixer_t
create(
  const char * jack_client_name_ptr,
  bool stereo);

void
destroy(
  jack_mixer_t mixer);

unsigned int
get_channels_count(
  jack_mixer_t mixer);

const char*
get_client_name(
  jack_mixer_t mixer);

int
get_last_midi_channel(
  jack_mixer_t mixer);

unsigned int
set_last_midi_channel(
  jack_mixer_t mixer,
  int new_channel);


int
get_midi_behavior_mode(
  jack_mixer_t mixer);

unsigned int
set_midi_behavior_mode(
  jack_mixer_t mixer,
  enum midi_behavior_mode mode);

jack_mixer_channel_t
add_channel(jack_mixer_t mixer,
  const char * channel_name,
  const char *send_name,
  double volume_initial,
  bool stereo);

const char *
channel_get_name(
  jack_mixer_channel_t channel);

const char *
  channel_get_current_send_name(
  jack_mixer_channel_t channel);

void
  channel_set_current_send_name(jack_mixer_channel_t channel,
  const char *name);

struct volume*
  channel_get_current_send_volume(
  jack_mixer_channel_t channel);

/* returned values are in dBFS */
void
channel_stereo_meter_read(
  jack_mixer_channel_t channel,
  double * left_ptr,
  double * right_ptr);

/* returned value is in dBFS */
void
channel_mono_meter_read(
  jack_mixer_channel_t channel,
  double * mono_ptr);

bool
channel_is_stereo(
  jack_mixer_channel_t channel);

void
channel_set_midi_change_callback(
  jack_mixer_channel_t channel,
  void (*midi_change_callback) (void*),
  void *user_data);

struct volume *new_volume(double volume);

/* volume is in dBFS */
void
channel_volume_write(
  jack_mixer_channel_t channel,
  double volume);

double
channel_volume_read(
  jack_mixer_channel_t channel);

void channel_volume_send_write(
  jack_mixer_channel_t channel,
  jack_mixer_output_channel_t output_channel,
  double volume);

double
  channel_volume_send_read(
  jack_mixer_channel_t channel,
  jack_mixer_output_channel_t output_channel);

void
channels_volumes_read(jack_mixer_t mixer_ptr);

/* balance is from -1.0 (full left) to +1.0 (full right) */
void
channel_balance_write(
  jack_mixer_channel_t channel,
  double balance);

double
channel_balance_read(
  jack_mixer_channel_t channel);

int
channel_get_balance_midi_cc(
  jack_mixer_channel_t channel);

unsigned int
channel_set_balance_midi_cc(
  jack_mixer_channel_t channel,
  int new_cc);

int
channel_get_volume_midi_cc(
  jack_mixer_channel_t channel);

unsigned int
channel_set_volume_midi_cc(
  jack_mixer_channel_t channel,
  int new_cc);

int
channel_get_mute_midi_cc(
  jack_mixer_channel_t channel);

unsigned int
channel_set_mute_midi_cc(
  jack_mixer_channel_t channel,
  int new_cc);

int
channel_get_solo_midi_cc(
  jack_mixer_channel_t channel);

unsigned int
channel_set_solo_midi_cc(
  jack_mixer_channel_t channel,
  int new_cc);

void channel_set_midi_cc_volume_picked_up(jack_mixer_channel_t channel,
  bool status);

void channel_set_midi_cc_balance_picked_up(jack_mixer_channel_t channel,
  bool status);

void
channel_autoset_volume_midi_cc(
  jack_mixer_channel_t channel);

void
channel_autoset_balance_midi_cc(
  jack_mixer_channel_t channel);

void
channel_autoset_mute_midi_cc(
  jack_mixer_channel_t channel);

void
channel_autoset_solo_midi_cc(
  jack_mixer_channel_t channel);

void free_frames(jack_mixer_frames_t frames);

void
remove_channel(
  jack_mixer_channel_t channel);

void
remove_channels(
  jack_mixer_t mixer);

/* returned value is in dBFS */
double
channel_abspeak_read(
  jack_mixer_channel_t channel);

void
channel_abspeak_reset(
  jack_mixer_channel_t channel);

void
channel_out_mute(
  jack_mixer_channel_t channel);

void
channel_out_unmute(
  jack_mixer_channel_t channel);

bool
channel_is_out_muted(
  jack_mixer_channel_t channel);

void
channel_solo(
  jack_mixer_channel_t channel);

void
channel_unsolo(
  jack_mixer_channel_t channel);

bool
channel_is_soloed(
  jack_mixer_channel_t channel);

void
channel_rename(
  jack_mixer_channel_t channel,
  const char * name);

void
channel_set_midi_scale(
  jack_mixer_channel_t channel,
  jack_mixer_scale_t scale);

bool
channel_get_midi_in_got_events(
  jack_mixer_channel_t channel);

jack_mixer_output_channel_t
add_output_channel(
  jack_mixer_t mixer,
  const char * channel_name,
  bool stereo,
  bool system);

void
remove_output_channel(
  jack_mixer_output_channel_t output_channel);

void
output_channel_set_solo(
  jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t channel,
  bool solo_value);

void
output_channel_set_muted(
  jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t channel,
  bool muted_value);

bool
output_channel_is_muted(
  jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t channel);

bool
output_channel_is_solo(
  jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t channel);

void
output_channel_set_prefader(
  jack_mixer_output_channel_t output_channel,
  bool pfl_value);

bool
output_channel_is_prefader(
  jack_mixer_output_channel_t output_channel);

void output_channel_set_in_prefader(jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t input_channel,
  bool prefader_value);

#endif /* #ifndef JACK_MIXER_H__DAEB51D8_5861_40F2_92E4_24CA495A384D__INCLUDED */
