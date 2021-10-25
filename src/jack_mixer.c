/* -*- Mode: C ; c-basic-offset: 2 -*- */
/*****************************************************************************
 *
 *   This file is part of jack_mixer
 *
 *   Copyright (C) 2006 Nedko Arnaudov <nedko@arnaudov.name>
 *   Copyright (C) 2009 Frederic Peters <fpeters@0d.be>
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

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <math.h>
#include <libintl.h>
#include <locale.h>
#include <jack/jack.h>
#if defined(HAVE_JACK_MIDI)
#include <jack/midiport.h>
#endif
#include <assert.h>
#include <pthread.h>

#include <glib.h>

#include "jack_mixer.h"
#include "log.h"

#define _(String) String

struct kmeter {
  float _z1;        // filter state
  float _z2;        // filter state
  float _rms;       // max rms value since last read()
  float _dpk;       // current digital peak value
  int _cnt;         // digital peak hold counter
  bool _flag;       // flag set by read(), resets _rms
  int _hold;        // number of JACK periods to hold peak value
  float _fall;      // per period fallback multiplier for peak value
  float _omega;     // ballistics filter constant.
};

struct channel {
  struct jack_mixer * mixer_ptr;
  char * name;
  bool stereo;
  bool out_mute;
  float volume_transition_seconds;
  unsigned int num_volume_transition_steps;
  float volume;
  jack_nframes_t volume_idx;
  float volume_new;
  float balance;
  jack_nframes_t balance_idx;
  float balance_new;
  float volume_left;
  float volume_left_new;
  float volume_right;
  float volume_right_new;
  float meter_left_postfader;
  float meter_left_prefader;
  float meter_right_postfader;
  float meter_right_prefader;
  float abspeak_postfader;
  float abspeak_prefader;
  struct kmeter kmeter_left;
  struct kmeter kmeter_right;
  struct kmeter kmeter_prefader_left;
  struct kmeter kmeter_prefader_right;

  jack_port_t * port_left;
  jack_port_t * port_right;

  jack_nframes_t peak_frames;
  float peak_left_prefader;
  float peak_left_postfader;
  float peak_right_prefader;
  float peak_right_postfader;

  jack_default_audio_sample_t * tmp_mixed_frames_left;
  jack_default_audio_sample_t * tmp_mixed_frames_right;
  jack_default_audio_sample_t * frames_left;
  jack_default_audio_sample_t * frames_right;
  jack_default_audio_sample_t * prefader_frames_left;
  jack_default_audio_sample_t * prefader_frames_right;

  jack_default_audio_sample_t * left_buffer_ptr;
  jack_default_audio_sample_t * right_buffer_ptr;

  bool NaN_detected;

  int8_t midi_cc_volume_index;
  int8_t midi_cc_balance_index;
  int8_t midi_cc_mute_index;
  int8_t midi_cc_solo_index;
  bool midi_cc_volume_picked_up;
  bool midi_cc_balance_picked_up;

  bool midi_in_got_events;
  int midi_out_has_events;
  void (*midi_change_callback) (void*);
  void *midi_change_callback_data;

  jack_mixer_scale_t midi_scale;
};

struct output_channel {
  struct channel channel;
  GSList *soloed_channels;
  GSList *muted_channels;
  GSList *prefader_channels;

  bool system; /* system channel, without any associated UI */
  bool prefader;
};

struct jack_mixer {
  pthread_mutex_t mutex;
  jack_client_t * jack_client;
  GSList *input_channels_list;
  GSList *output_channels_list;
  GSList *soloed_channels;

  jack_port_t * port_midi_in;
  jack_port_t * port_midi_out;

  bool kmetering;

  int8_t last_midi_cc;
  enum midi_behavior_mode midi_behavior;

  struct channel* midi_cc_map[128];
};

static jack_mixer_output_channel_t
create_output_channel(
  jack_mixer_t mixer,
  const char * channel_name,
  bool stereo,
  bool system);

static inline void
update_channel_buffers(
  struct channel * channel_ptr,
  jack_nframes_t nframes);

static void
unset_midi_cc_mapping(
  struct jack_mixer * mixer,
  int8_t cc);

float
value_to_db(
  float value)
{
  if (value <= 0)
  {
    return -INFINITY;
  }

  return 20.0 * log10f(value);
}

float
db_to_value(
  float db)
{
  return powf(10.0, db / 20.0);
}

double
interpolate(
  double start,
  double end,
  int step,
  int steps)
{
  double ret;
  double frac = 0.01;
  LOG_DEBUG("Interpolation: start=%f -> end=%f, step=%d\n", start, end, step);
  if (start <= 0) {
    if (step <= frac * steps) {
      ret = frac * end * step / steps;
    }
    else {
      ret = db_to_value(value_to_db(frac * end) + (value_to_db(end) - value_to_db(frac * end)) * step / steps);;
    }
  }
  else if (end <= 0) {
    if (step >= (1 - frac) * steps) {
      ret = frac * start - frac * start * step / steps;
    }
    else {
      ret = db_to_value(value_to_db(start) + (value_to_db(frac * start) - value_to_db(start)) * step / steps);
    }
  }
  else {
    ret = db_to_value(value_to_db(start) + (value_to_db(end) - value_to_db(start)) *step /steps);
  }
  LOG_DEBUG("Interpolated value: %f\n", ret);
  return ret;
}


const char* const _jack_mixer_error_str[] = {
  /* JACK_MIXER_NO_ERROR */
  _("No error.\n"),
  /* JACK_MIXER_ERROR_JACK_CLIENT_CREATE */
  _("Could not create JACK client.\nPlease make sure JACK daemon is running.\n"),
  /* JACK_MIXER_ERROR_JACK_MIDI_IN_CREATE */
  _("Could not create JACK MIDI in port.\n"),
  /* JACK_MIXER_ERROR_JACK_MIDI_OUT_CREATE */
  _("Could not create JACK MIDI out port.\n"),
  /* JACK_MIXER_ERROR_JACK_SET_PROCESS_CALLBACK */
  _("Could not set JACK process callback.\n"),
  /* JACK_MIXER_ERROR_JACK_SET_BUFFER_SIZE_CALLBACK */
  _("Could not set JACK buffer size callback.\n"),
  /* JACK_MIXER_ERROR_JACK_ACTIVATE */
  _("Could not activate JACK client.\n"),
  /* JACK_MIXER_ERROR_CHANNEL_MALLOC */
  _("Could not allocate memory for channel.\n"),
  /* JACK_MIXER_ERROR_CHANNEL_NAME_MALLOC */
  _("Could not allocate memory for channel name.\n"),
  /* JACK_MIXER_ERROR_PORT_REGISTER */
  _("Could not register JACK port for channel.\n"),
  /* JACK_MIXER_ERROR_PORT_REGISTER_LEFT */
  _("Could not register JACK port for left channel.\n"),
  /* JACK_MIXER_ERROR_PORT_REGISTER_RIGHT */
  _("Could not register JACK port for right channel.\n"),
  /* JACK_MIXER_ERROR_JACK_RENAME_PORT */
  _("Could not rename JACK port for channel.\n"),
  /* JACK_MIXER_ERROR_JACK_RENAME_PORT_LEFT */
  _("Could not rename JACK port for left channel.\n"),
  /* JACK_MIXER_ERROR_JACK_RENAME_PORT_LEFT */
  _("Could not rename JACK port for right channel.\n"),
  /* JACK_MIXER_ERROR_PORT_NAME_MALLOC */
  _("Could not allocate memory for port name.\n"),
  /* JACK_MIXER_ERROR_INVALID_CC */
  _("Control Change number out of range.\n"),
  /* JACK_MIXER_ERROR_NO_FREE_CC */
  _("No free Control Change number.\n")
};

jack_mixer_error_t _jack_mixer_error = JACK_MIXER_NO_ERROR;

/*****************************************************************************/
/* Public API */

jack_mixer_error_t
jack_mixer_error()
{
  return _jack_mixer_error;
}

const char*
jack_mixer_error_str()
{
  const char* err_str = NULL;

  /* Ensure error codes are within valid range */
  if (_jack_mixer_error == JACK_MIXER_NO_ERROR || _jack_mixer_error >= JACK_MIXER_ERROR_COUNT)
  {
    goto done;
  }

  err_str = gettext(_jack_mixer_error_str[_jack_mixer_error]);

done:
  return err_str;
}

#define channel_ptr ((struct channel *)channel)

const char*
channel_get_name(
  jack_mixer_channel_t channel)
{
  return channel_ptr->name;
}

int
channel_rename(
  jack_mixer_channel_t channel,
  const char * name)
{
  char * new_name;
  size_t channel_name_size;
  char * port_name;
  int ret;

  new_name = strdup(name);
  if (new_name == NULL)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_PORT_NAME_MALLOC;
    goto fail;
  }

  if (channel_ptr->name)
  {
    free(channel_ptr->name);
  }

  channel_ptr->name = new_name;

  if (channel_ptr->stereo)
  {
    channel_name_size = strlen(name);
    port_name = malloc(channel_name_size + 3);
    memcpy(port_name, name, channel_name_size);

    port_name[channel_name_size] = ' ';
    port_name[channel_name_size+1] = 'L';
    port_name[channel_name_size+2] = 0;

    ret = jack_port_rename(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_left, port_name);
    if (ret != 0)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_JACK_RENAME_PORT_LEFT;
      goto fail;
    }

    port_name[channel_name_size+1] = 'R';

    ret = jack_port_rename(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_right, port_name);
    if (ret != 0)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_JACK_RENAME_PORT_RIGHT;
      goto fail_free;
    }

    free(port_name);
  }
  else
  {
    ret = jack_port_rename(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_left, name);
    if (ret != 0)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_JACK_RENAME_PORT;
      goto fail;
    }
  }
  return 0;
fail_free:
  free(port_name);
fail:
  return -1;
}

bool
channel_is_stereo(
  jack_mixer_channel_t channel)
{
  return channel_ptr->stereo;
}

int8_t
channel_get_balance_midi_cc(
  jack_mixer_channel_t channel)
{
  return channel_ptr->midi_cc_balance_index;
}

/*
 * Remove assignment for given MIDI CC
 *
 * This is an internal (static) function
 */
static void
unset_midi_cc_mapping(
  struct jack_mixer * mixer,
  int8_t cc)
{
  struct channel *channel = mixer->midi_cc_map[cc];
  if (!channel) {
    return;
  }

  if (channel->midi_cc_volume_index == cc) {
    channel->midi_cc_volume_index = -1;
  }
  else if (channel->midi_cc_balance_index == cc) {
    channel->midi_cc_balance_index = -1;
  }
  else if (channel->midi_cc_mute_index == cc) {
    channel->midi_cc_mute_index = -1;
  }
  else if (channel->midi_cc_solo_index == cc) {
    channel->midi_cc_solo_index = -1;
  }

  mixer->midi_cc_map[cc] = NULL;
}

int
channel_set_balance_midi_cc(
  jack_mixer_channel_t channel,
  int8_t new_cc)
{
  if (new_cc < 0) {
    _jack_mixer_error = JACK_MIXER_ERROR_INVALID_CC;
    return -1;
  }

  /* Remove previous assignment for this CC */
  unset_midi_cc_mapping(channel_ptr->mixer_ptr, new_cc);
  /* Remove previous balance CC mapped to this channel (if any) */
  if (channel_ptr->midi_cc_balance_index != -1) {
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] = NULL;
  }
  channel_ptr->mixer_ptr->midi_cc_map[new_cc] = channel_ptr;
  channel_ptr->midi_cc_balance_index = new_cc;
  return 0;
}

int8_t
channel_get_volume_midi_cc(
  jack_mixer_channel_t channel)
{
  return channel_ptr->midi_cc_volume_index;
}

int
channel_set_volume_midi_cc(
  jack_mixer_channel_t channel,
  int8_t new_cc)
{
  if (new_cc < 0) {
    _jack_mixer_error = JACK_MIXER_ERROR_INVALID_CC;
    return -1;
  }

  /* remove previous assignment for this CC */
  unset_midi_cc_mapping(channel_ptr->mixer_ptr, new_cc);
  /* remove previous volume CC mapped to this channel (if any) */
  if (channel_ptr->midi_cc_volume_index != -1) {
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] = NULL;
  }
  channel_ptr->mixer_ptr->midi_cc_map[new_cc] = channel_ptr;
  channel_ptr->midi_cc_volume_index = new_cc;
  return 0;
}

int8_t
channel_get_mute_midi_cc(
  jack_mixer_channel_t channel)
{
  return channel_ptr->midi_cc_mute_index;
}

int
channel_set_mute_midi_cc(
  jack_mixer_channel_t channel,
  int8_t new_cc)
{
  if (new_cc < 0) {
    _jack_mixer_error = JACK_MIXER_ERROR_INVALID_CC;
    return -1;
  }

  /* Remove previous assignment for this CC */
  unset_midi_cc_mapping(channel_ptr->mixer_ptr, new_cc);
  /* Remove previous mute CC mapped to this channel (if any) */
  if (channel_ptr->midi_cc_mute_index != -1) {
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_mute_index] = NULL;
  }
  channel_ptr->mixer_ptr->midi_cc_map[new_cc] = channel_ptr;
  channel_ptr->midi_cc_mute_index = new_cc;
  return 0;
}

int8_t
channel_get_solo_midi_cc(
  jack_mixer_channel_t channel)
{
  return channel_ptr->midi_cc_solo_index;
}

void
channel_set_midi_cc_volume_picked_up(
  jack_mixer_channel_t channel,
  bool status)
{
  LOG_DEBUG("Setting channel %s volume picked up to %d.\n", channel_ptr->name, status);
  channel_ptr->midi_cc_volume_picked_up = status;
}

void
channel_set_midi_cc_balance_picked_up(
  jack_mixer_channel_t channel,
  bool status)
{
  LOG_DEBUG("Setting channel %s balance picked up to %d.\n", channel_ptr->name, status);
  channel_ptr->midi_cc_balance_picked_up = status;
}

int
channel_set_solo_midi_cc(
  jack_mixer_channel_t channel,
  int8_t new_cc)
{
  if (new_cc < 0) {
    _jack_mixer_error = JACK_MIXER_ERROR_INVALID_CC;
    return -1;
  }

  /* Remove previous assignment for this CC */
  unset_midi_cc_mapping(channel_ptr->mixer_ptr, new_cc);
  /* Remove previous solo CC mapped to this channel (if any) */
  if (channel_ptr->midi_cc_solo_index != -1) {
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_solo_index] = NULL;
  }
  channel_ptr->mixer_ptr->midi_cc_map[new_cc] = channel_ptr;
  channel_ptr->midi_cc_solo_index = new_cc;
  return 0;
}

int
channel_autoset_volume_midi_cc(
  jack_mixer_channel_t channel)
{
  struct jack_mixer *mixer_ptr = channel_ptr->mixer_ptr;

  for (int i = 11 ; i < 128 ; i++)
  {
    if (!mixer_ptr->midi_cc_map[i])
    {
      mixer_ptr->midi_cc_map[i] = channel_ptr;
      channel_ptr->midi_cc_volume_index = i;

      LOG_DEBUG("New channel \"%s\" volume mapped to CC#%i.\n", channel_ptr->name, i);
      return i;
    }
  }
  _jack_mixer_error = JACK_MIXER_ERROR_NO_FREE_CC;
  return -1;
}

int
channel_autoset_balance_midi_cc(
  jack_mixer_channel_t channel)
{
  struct jack_mixer *mixer_ptr = channel_ptr->mixer_ptr;

  for (int i = 11; i < 128 ; i++)
  {
    if (!mixer_ptr->midi_cc_map[i])
    {
      mixer_ptr->midi_cc_map[i] = channel_ptr;
      channel_ptr->midi_cc_balance_index = i;

      LOG_DEBUG("New channel \"%s\" balance mapped to CC#%i.\n", channel_ptr->name, i);
      return i;
    }
  }
  _jack_mixer_error = JACK_MIXER_ERROR_NO_FREE_CC;
  return -1;
}

int
channel_autoset_mute_midi_cc(
  jack_mixer_channel_t channel)
{
  struct jack_mixer *mixer_ptr = channel_ptr->mixer_ptr;

  for (int i = 11; i < 128 ; i++)
  {
    if (!mixer_ptr->midi_cc_map[i])
    {
      mixer_ptr->midi_cc_map[i] = channel_ptr;
      channel_ptr->midi_cc_mute_index = i;

      LOG_DEBUG("New channel \"%s\" mute mapped to CC#%i.\n", channel_ptr->name, i);
      return i;
    }
  }
  _jack_mixer_error = JACK_MIXER_ERROR_NO_FREE_CC;
  return -1;
}

int
channel_autoset_solo_midi_cc(
  jack_mixer_channel_t channel)
{
  struct jack_mixer *mixer_ptr = channel_ptr->mixer_ptr;

  for (int i = 11; i < 128 ; i++)
  {
    if (!mixer_ptr->midi_cc_map[i])
    {
      mixer_ptr->midi_cc_map[i] = channel_ptr;
      channel_ptr->midi_cc_solo_index = i;

      LOG_DEBUG("New channel \"%s\" solo mapped to CC#%i.\n", channel_ptr->name, i);
      return i;
    }
  }
  _jack_mixer_error = JACK_MIXER_ERROR_NO_FREE_CC;
  return -1;
}

void
remove_channel(
  jack_mixer_channel_t channel)
{
  GSList *list_ptr;
  channel_ptr->mixer_ptr->input_channels_list = g_slist_remove(
                  channel_ptr->mixer_ptr->input_channels_list, channel_ptr);
  free(channel_ptr->name);

  /* remove references to input channel from all output channels */
  for (list_ptr = channel_ptr->mixer_ptr->output_channels_list; list_ptr; list_ptr = g_slist_next(list_ptr))
  {
    struct output_channel *output_channel_ptr = list_ptr->data;
    output_channel_set_solo(output_channel_ptr, channel, false);
    output_channel_set_muted(output_channel_ptr, channel, false);
  }

  jack_port_unregister(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_left);
  if (channel_ptr->stereo)
  {
    jack_port_unregister(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_right);
  }

  if (channel_ptr->midi_cc_volume_index != -1)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] = NULL;
  }

  if (channel_ptr->midi_cc_balance_index != -1)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] = NULL;
  }

  if (channel_ptr->midi_cc_mute_index != -1)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_mute_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_mute_index] = NULL;
  }
  if (channel_ptr->midi_cc_solo_index != -1)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_solo_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_solo_index] = NULL;
  }

  free(channel_ptr->frames_left);
  free(channel_ptr->frames_right);
  free(channel_ptr->prefader_frames_left);
  free(channel_ptr->prefader_frames_right);
  free(channel_ptr);
}

void
channel_stereo_meter_read(
  jack_mixer_channel_t channel,
  double * left_ptr,
  double * right_ptr,
  enum meter_mode mode)
{
  assert(channel_ptr);
  if (mode == Pre_Fader) {
    *left_ptr = value_to_db(channel_ptr->meter_left_prefader);
    *right_ptr = value_to_db(channel_ptr->meter_right_prefader);
  } else {
    *left_ptr = value_to_db(channel_ptr->meter_left_postfader);
    *right_ptr = value_to_db(channel_ptr->meter_right_postfader);
  }
}


void
channel_mono_meter_read(
  jack_mixer_channel_t channel,
  double * mono_ptr,
  enum meter_mode mode)
{
  if (mode == Pre_Fader) {
    *mono_ptr = value_to_db(channel_ptr->meter_left_prefader);
  } else {
    *mono_ptr = value_to_db(channel_ptr->meter_left_postfader);
  }
}

void
channel_stereo_kmeter_read(
  jack_mixer_channel_t channel,
  double * left_ptr,
  double * right_ptr,
  double * left_rms_ptr,
  double * right_rms_ptr,
  enum meter_mode mode)
{
  struct kmeter *kmeter_left;
  struct kmeter *kmeter_right;
  assert(channel_ptr);
  if (mode == Pre_Fader) {
    kmeter_left = &channel_ptr->kmeter_prefader_left;
    kmeter_right = &channel_ptr->kmeter_prefader_right;
  } else {
    kmeter_left = &channel_ptr->kmeter_left;
    kmeter_right = &channel_ptr->kmeter_right;
  }
  *left_ptr = value_to_db(kmeter_left->_dpk);
  *right_ptr = value_to_db(kmeter_right->_dpk);
  *left_rms_ptr = value_to_db(kmeter_left->_rms);
  *right_rms_ptr = value_to_db(kmeter_right->_rms);
  kmeter_left->_flag = true;
  kmeter_right->_flag = true;
}

void
channel_mono_kmeter_read(
  jack_mixer_channel_t channel,
  double * mono_ptr,
  double * mono_rms_ptr,
  enum meter_mode mode)
{
  struct kmeter *kmeter;
  if (mode == Pre_Fader) {
    kmeter = &channel_ptr->kmeter_prefader_left;
  } else {
    kmeter = &channel_ptr->kmeter_left;
  }
  *mono_ptr = value_to_db(kmeter->_dpk);
  *mono_rms_ptr = value_to_db(kmeter->_rms);
  kmeter->_flag = true;
}

void
channel_mono_kmeter_reset(
  jack_mixer_channel_t channel)
{
  struct kmeter *kmeter;
  kmeter = &channel_ptr->kmeter_prefader_left;
  kmeter->_flag = true;
  kmeter = &channel_ptr->kmeter_left;
  kmeter->_flag = true;
}

void
channel_stereo_kmeter_reset(
  jack_mixer_channel_t channel)
{
  struct kmeter *kmeter;
  channel_mono_kmeter_reset(channel);
  kmeter = &channel_ptr->kmeter_prefader_right;
  kmeter->_flag = true;
  kmeter = &channel_ptr->kmeter_right;
  kmeter->_flag = true;
}

void
channel_volume_write(
  jack_mixer_channel_t channel,
  double volume)
{
  assert(channel_ptr);
  double value = db_to_value(volume);
  /*If changing volume and find we're in the middle of a previous transition,
   *then set current volume to place in transition to avoid a jump.*/
  if (channel_ptr->volume_new != channel_ptr->volume) {
    channel_ptr->volume = interpolate(channel_ptr->volume,
                                      channel_ptr->volume_new,
                                      channel_ptr->volume_idx,
                                      channel_ptr->num_volume_transition_steps);
  }
  channel_ptr->volume_idx = 0;
  if (channel_ptr->volume_new != value) {
    channel_ptr->midi_out_has_events |= CHANNEL_VOLUME;
  }
  channel_ptr->volume_new = value;
  LOG_DEBUG("\"%s\" volume -> %f.\n", channel_ptr->name, value);
}

double
channel_volume_read(
  jack_mixer_channel_t channel)
{
  assert(channel_ptr);
  return value_to_db(channel_ptr->volume_new);
}

void
channels_volumes_read(
  jack_mixer_t mixer_ptr)
{
    GSList *node_ptr;
    struct channel *pChannel;
    struct jack_mixer * pMixer = (struct jack_mixer *)mixer_ptr;

    for (node_ptr = pMixer->input_channels_list; node_ptr; node_ptr = g_slist_next(node_ptr))
    {
        pChannel = (struct channel *)node_ptr->data;
        double vol = channel_volume_read( (jack_mixer_channel_t)pChannel);
        printf(gettext("%s: volume is %f dbFS for mixer channel: %s\n"),
               jack_get_client_name(pMixer->jack_client), vol, pChannel->name);
    }
}

void
channel_balance_write(
  jack_mixer_channel_t channel,
  double balance)
{
  assert(channel_ptr);
  if (channel_ptr->balance != channel_ptr->balance_new) {
    channel_ptr->balance = channel_ptr->balance + channel_ptr->balance_idx *
      (channel_ptr->balance_new - channel_ptr->balance) /
      channel_ptr->num_volume_transition_steps;
  }
  channel_ptr->balance_idx = 0;
  if (channel_ptr->balance_new != balance) {
    channel_ptr->midi_out_has_events |= CHANNEL_BALANCE;
  }
  channel_ptr->balance_new = balance;
  LOG_DEBUG("\"%s\" balance -> %f\n", channel_ptr->name, balance);
}

double
channel_balance_read(
  jack_mixer_channel_t channel)
{
  assert(channel_ptr);
  return channel_ptr->balance_new;
}

double
channel_abspeak_read(
  jack_mixer_channel_t channel,
  enum meter_mode mode)
{
  assert(channel_ptr);
  if (channel_ptr->NaN_detected)
  {
    return sqrt(-1);
  }
  else
  {
    return value_to_db(mode == Post_Fader ? channel_ptr->abspeak_postfader : channel_ptr->abspeak_prefader);
  }
}

void
channel_abspeak_reset(
  jack_mixer_channel_t channel,
  enum meter_mode mode)
{
  if (mode == Post_Fader) {
    channel_ptr->abspeak_postfader = 0;
  } else if (mode == Pre_Fader) {
    channel_ptr->abspeak_prefader = 0;
  }
  channel_ptr->NaN_detected = false;
}

void
channel_out_mute(
  jack_mixer_channel_t channel)
{
  if (!channel_ptr->out_mute) {
    channel_ptr->out_mute = true;
    channel_ptr->midi_out_has_events |= CHANNEL_MUTE;
    LOG_DEBUG("\"%s\" muted.\n", channel_ptr->name);
  }
}

void
channel_out_unmute(
  jack_mixer_channel_t channel)
{
  if (channel_ptr->out_mute) {
    channel_ptr->out_mute = false;
    channel_ptr->midi_out_has_events |= CHANNEL_MUTE;
    LOG_DEBUG("\"%s\" un-muted.\n", channel_ptr->name);
  }
}

bool
channel_is_out_muted(
  jack_mixer_channel_t channel)
{
  return channel_ptr->out_mute;
}

void
channel_solo(
  jack_mixer_channel_t channel)
{
  if (g_slist_find(channel_ptr->mixer_ptr->soloed_channels, channel) != NULL)
    return;
  channel_ptr->mixer_ptr->soloed_channels = g_slist_prepend(channel_ptr->mixer_ptr->soloed_channels, channel);
  channel_ptr->midi_out_has_events |= CHANNEL_SOLO;
  LOG_DEBUG("\"%s\" soloed.\n", channel_ptr->name);
}

void
channel_unsolo(
  jack_mixer_channel_t channel)
{
  if (g_slist_find(channel_ptr->mixer_ptr->soloed_channels, channel) == NULL)
    return;
  channel_ptr->mixer_ptr->soloed_channels = g_slist_remove(channel_ptr->mixer_ptr->soloed_channels, channel);
  channel_ptr->midi_out_has_events |= CHANNEL_SOLO;
  LOG_DEBUG("\"%s\" un-soloed.\n", channel_ptr->name);
}

bool
channel_is_soloed(
  jack_mixer_channel_t channel)
{
  if (g_slist_find(channel_ptr->mixer_ptr->soloed_channels, channel))
    return true;
  return false;
}

void
channel_set_midi_scale(
  jack_mixer_channel_t channel,
  jack_mixer_scale_t scale)
{
  channel_ptr->midi_scale = scale;
}

void
channel_set_midi_change_callback(
  jack_mixer_channel_t channel,
  void (*midi_change_callback) (void*),
  void *user_data)
{
  channel_ptr->midi_change_callback = midi_change_callback;
  channel_ptr->midi_change_callback_data = user_data;
}

bool
channel_get_midi_in_got_events(
  jack_mixer_channel_t channel)
{
  bool t = channel_ptr->midi_in_got_events;
  channel_ptr->midi_in_got_events = false;
  return t;
}

#undef channel_ptr

/*
 * Process input channels and mix them into one output channel signal
 */
static inline void
mix_one(
  struct output_channel *output_mix_channel,
  GSList *channels_list,        /* All input channels */
  jack_nframes_t start,         /* Index of first sample to process */
  jack_nframes_t end)           /* Index of sample to stop processing before */
{
  jack_nframes_t i;

  GSList *node_ptr;
  struct channel * channel_ptr;
  jack_default_audio_sample_t frame_left;
  jack_default_audio_sample_t frame_right;
  jack_default_audio_sample_t frame_left_pre;
  jack_default_audio_sample_t frame_right_pre;

  struct channel *mix_channel = (struct channel*)output_mix_channel;

  /* Zero intermediate mix & output buffers */
  for (i = start; i < end; i++)
  {
    mix_channel->left_buffer_ptr[i] = mix_channel->tmp_mixed_frames_left[i] = 0.0;
    if (mix_channel->stereo)
      mix_channel->right_buffer_ptr[i] = mix_channel->tmp_mixed_frames_right[i] = 0.0;
  }

  /* For each input channel: */
  for (node_ptr = channels_list; node_ptr; node_ptr = g_slist_next(node_ptr))
  {
    channel_ptr = node_ptr->data;

    /* Skip input channels with activated mute for this output channel */
    if (g_slist_find(output_mix_channel->muted_channels, channel_ptr) != NULL || channel_ptr->out_mute) {
      continue;
    }

    /* Mix signal of all input channels going to this output channel:
     *
     * Only add the signal from this input channel:
     *
     * - if there are no globally soloed channels and no soloed channels for this output-channel;
     * - or if the input channel is globally soloed and the output channel is not a system
     *   channel (direct out or monitor out);
     * - or if the input channel is soloed for this output channel.
     *
     * */
    if ((!channel_ptr->mixer_ptr->soloed_channels && !output_mix_channel->soloed_channels) ||
        (channel_ptr->mixer_ptr->soloed_channels &&
         g_slist_find(channel_ptr->mixer_ptr->soloed_channels, channel_ptr) != NULL &&
         !output_mix_channel->system) ||
        (output_mix_channel->soloed_channels &&
         g_slist_find(output_mix_channel->soloed_channels, channel_ptr) != NULL))
    {

      /* Get either post or pre-fader signal */
      for (i = start ; i < end ; i++)
      {
        /* Left/mono signal */
        if (! output_mix_channel->prefader &&
            g_slist_find(output_mix_channel->prefader_channels, channel_ptr) == NULL)
        {
          frame_left = channel_ptr->frames_left[i-start];
        }
        else {
          /* Output channel is globally set to pre-fader routing or
           * input channel has pre-fader routing set for this output channel
           */
          frame_left = channel_ptr->prefader_frames_left[i-start];
        }

        if (frame_left == NAN)
          break;

        mix_channel->tmp_mixed_frames_left[i] += frame_left;

        /* Right signal */
        if (mix_channel->stereo)
        {
          if (! output_mix_channel->prefader &&
              g_slist_find(output_mix_channel->prefader_channels, channel_ptr) == NULL)
          {
            frame_right = channel_ptr->frames_right[i-start];
          }
          else {
            /* Pre-fader routing */
            frame_right = channel_ptr->prefader_frames_right[i-start];
          }

          if (frame_right == NAN)
            break;

          mix_channel->tmp_mixed_frames_right[i] += frame_right;
        }
      }
    }
  }

  /* Apply output channel volume and compute meter signal and peak values */
  unsigned int steps = mix_channel->num_volume_transition_steps;

  for (i = start ; i < end ; i++)
  {
    mix_channel->prefader_frames_left[i] = mix_channel->tmp_mixed_frames_left[i];
    mix_channel->prefader_frames_right[i] = mix_channel->tmp_mixed_frames_right[i];
    /** Apply fader volume if output channel is not set to pre-fader routing */
    if (! output_mix_channel->prefader) {
      float volume = mix_channel->volume;
      float volume_new = mix_channel->volume_new;
      float vol = volume;
      float balance = mix_channel->balance;
      float balance_new = mix_channel->balance_new;
      float bal = balance;

      /* Do interpolation during transition to target volume level */
      if (volume != volume_new) {
        vol = interpolate(volume, volume_new, mix_channel->volume_idx, steps);
      }

      /* Do interpolation during transition to target balance */
      if (balance != balance_new) {
        bal = mix_channel->balance_idx * (balance_new - balance) / steps + balance;
      }

      float vol_l;
      float vol_r;

      /* Calculate left+right gain from volume and balance levels */
      if (mix_channel->stereo) {
        if (bal > 0) {
          vol_l = vol * (1 - bal);
          vol_r = vol;
        }
        else {
          vol_l = vol;
          vol_r = vol * (1 + bal);
        }
      }
      else {
        vol_l = vol * (1 - bal);
        vol_r = vol * (1 + bal);
      }

      /* Apply gain to output mix */
      mix_channel->tmp_mixed_frames_left[i] *= vol_l;
      mix_channel->tmp_mixed_frames_right[i] *= vol_r;
    }


    /* Get peak signal, left/right and combined */
    frame_left = fabsf(mix_channel->tmp_mixed_frames_left[i]);
    frame_left_pre = fabsf(mix_channel->prefader_frames_left[i]);

    if (mix_channel->peak_left_prefader < frame_left_pre)
    {
      mix_channel->peak_left_prefader = frame_left_pre;
    }

    if (mix_channel->peak_left_postfader < frame_left)
    {
      mix_channel->peak_left_postfader = frame_left;
    }

    if (frame_left > mix_channel->abspeak_postfader)
    {
      mix_channel->abspeak_postfader = frame_left;
    }

    if (frame_left_pre > mix_channel->abspeak_prefader)
    {
      mix_channel->abspeak_prefader = frame_left_pre;
    }

    /* This seems to duplicate what was already done right above? */
    if (mix_channel->stereo)
    {
      frame_right = fabsf(mix_channel->tmp_mixed_frames_right[i]);
      frame_right_pre = fabsf(mix_channel->prefader_frames_right[i]);

      if (mix_channel->peak_right_prefader < frame_right_pre)
      {
        mix_channel->peak_right_prefader = frame_right_pre;
      }

      if (mix_channel->peak_right_postfader < frame_right)
      {
        mix_channel->peak_right_postfader = frame_right;
      }

      if (frame_right > mix_channel->abspeak_postfader)
      {
        mix_channel->abspeak_postfader = frame_right;
      }

      if (frame_right_pre > mix_channel->abspeak_prefader)
      {
        mix_channel->abspeak_prefader = frame_right_pre;
      }
    }

    /* update left/right peak values every so often */
    mix_channel->peak_frames++;
    if (mix_channel->peak_frames >= PEAK_FRAMES_CHUNK)
    {
      mix_channel->meter_left_prefader = mix_channel->peak_left_prefader;
      mix_channel->peak_left_prefader = 0.0;

      mix_channel->meter_left_postfader = mix_channel->peak_left_postfader;
      mix_channel->peak_left_postfader = 0.0;

      if (mix_channel->stereo)
      {
        mix_channel->meter_right_prefader = mix_channel->peak_right_prefader;
        mix_channel->peak_right_prefader = 0.0;

        mix_channel->meter_right_postfader = mix_channel->peak_right_postfader;
        mix_channel->peak_right_postfader = 0.0;
      }

      mix_channel->peak_frames = 0;
    }

    /* Finish off volume interpolation */
    mix_channel->volume_idx++;
    if ((mix_channel->volume != mix_channel->volume_new) && (mix_channel->volume_idx == steps)) {
      mix_channel->volume = mix_channel->volume_new;
      mix_channel->volume_idx = 0;
    }
    /* Finish off volume interpolation */
    mix_channel->balance_idx++;
    if ((mix_channel->balance != mix_channel->balance_new) && (mix_channel->balance_idx == steps)) {
      mix_channel->balance = mix_channel->balance_new;
      mix_channel->balance_idx = 0;
    }

    /* Finally, if output channel is not muted, put signal into output buffer */
    if (!mix_channel->out_mute) {
        mix_channel->left_buffer_ptr[i] = mix_channel->tmp_mixed_frames_left[i];
        if (mix_channel->stereo)
          mix_channel->right_buffer_ptr[i] = mix_channel->tmp_mixed_frames_right[i];
    }
  }

  /* Calculate k-metering for output channel*/

  if (mix_channel->mixer_ptr->kmetering) {
    kmeter_process(&mix_channel->kmeter_left, mix_channel->tmp_mixed_frames_left, start, end);
    kmeter_process(&mix_channel->kmeter_right, mix_channel->tmp_mixed_frames_right, start, end);
    kmeter_process(&mix_channel->kmeter_prefader_left, mix_channel->prefader_frames_left, start, end);
    kmeter_process(&mix_channel->kmeter_prefader_right, mix_channel->prefader_frames_right, start, end);
  }
}

static inline void
calc_channel_frames(
  struct channel *channel_ptr,
  jack_nframes_t start,
  jack_nframes_t end)
{
  jack_nframes_t i;
  jack_default_audio_sample_t frame_left = 0.0f;
  jack_default_audio_sample_t frame_right = 0.0f;
  jack_default_audio_sample_t frame_left_pre = 0.0f;
  jack_default_audio_sample_t frame_right_pre = 0.0f;
  unsigned int steps = channel_ptr->num_volume_transition_steps;

  for (i = start ; i < end ; i++)
  {
    if (i-start >= MAX_BLOCK_SIZE)
    {
      fprintf(stderr, "i-start too high: %d - %d\n", i, start);
    }

    /* Save pre-fader signal */
    channel_ptr->prefader_frames_left[i-start] = channel_ptr->left_buffer_ptr[i];
    if (channel_ptr->stereo)
      channel_ptr->prefader_frames_right[i-start] = channel_ptr->right_buffer_ptr[i];

    /* Detect de-normals */
    if (!FLOAT_EXISTS(channel_ptr->left_buffer_ptr[i]))
    {
      channel_ptr->NaN_detected = true;
      channel_ptr->frames_left[i-start] = NAN;
      break;
    }

    /* Get current and target channel volume and balance. */
    float volume = channel_ptr->volume;
    float volume_new = channel_ptr->volume_new;
    float vol = volume;
    float balance = channel_ptr->balance;
    float balance_new = channel_ptr->balance_new;
    float bal = balance;

    /* During transition do interpolation to target volume level */
    if (channel_ptr->volume != channel_ptr->volume_new) {
      vol = interpolate(volume, volume_new, channel_ptr->volume_idx, steps);
    }

    /* During transition do interpolation to target balance */
    if (channel_ptr->balance != channel_ptr->balance_new) {
      bal = channel_ptr->balance_idx * (balance_new - balance) / steps + balance;
    }

    /* Calculate left+right gain from volume and balance levels */
    float vol_l;
    float vol_r;
    if (channel_ptr->stereo) {
      if (bal > 0) {
        vol_l = vol * (1 - bal);
        vol_r = vol;
      }
      else {
        vol_l = vol;
        vol_r = vol * (1 + bal);
      }
    }
    else {
      vol_l = vol * (1 - bal);
      vol_r = vol * (1 + bal);
    }

    /* Calculate left channel post-fader sample */
    frame_left = channel_ptr->left_buffer_ptr[i] * vol_l;
    frame_left_pre = channel_ptr->left_buffer_ptr[i];

    /* Calculate right channel post-fader sample */
    if (channel_ptr->stereo)
    {
      if (!FLOAT_EXISTS(channel_ptr->right_buffer_ptr[i]))
      {
        channel_ptr->NaN_detected = true;
        channel_ptr->frames_right[i-start] = NAN;
        break;
      }

      frame_right = channel_ptr->right_buffer_ptr[i] * vol_r;
      frame_right_pre = channel_ptr->right_buffer_ptr[i];
    }
    else
    {
      frame_right = channel_ptr->left_buffer_ptr[i] * vol_r;
      frame_right_pre = channel_ptr->left_buffer_ptr[i];
    }
    channel_ptr->frames_left[i-start] = frame_left;
    channel_ptr->frames_right[i-start] = frame_right;

    /* Calculate left+right peak-level and, if need be,
     * update abspeak level
     */
    if (channel_ptr->stereo)
    {
      frame_left = fabsf(frame_left);
      frame_right = fabsf(frame_right);
      frame_left_pre = fabsf(frame_left_pre);
      frame_right_pre = fabsf(frame_right_pre);

      if (channel_ptr->peak_left_prefader < frame_left_pre)
      {
        channel_ptr->peak_left_prefader = frame_left_pre;
      }

      if (channel_ptr->peak_left_postfader < frame_left)
      {
        channel_ptr->peak_left_postfader = frame_left;
      }

      if (frame_left > channel_ptr->abspeak_postfader)
      {
        channel_ptr->abspeak_postfader = frame_left;
      }

      if (frame_left_pre > channel_ptr->abspeak_prefader)
      {
        channel_ptr->abspeak_prefader = frame_left_pre;
      }

      if (channel_ptr->peak_right_prefader < frame_right_pre)
      {
        channel_ptr->peak_right_prefader = frame_right_pre;
      }

      if (channel_ptr->peak_right_postfader < frame_right)
      {
        channel_ptr->peak_right_postfader = frame_right;
      }

      if (frame_right > channel_ptr->abspeak_postfader)
      {
        channel_ptr->abspeak_postfader = frame_right;
      }

      if (frame_right_pre > channel_ptr->abspeak_prefader)
      {
        channel_ptr->abspeak_prefader = frame_right_pre;
      }
    }
    else
    {
      frame_left = (fabsf(frame_left) + fabsf(frame_right)) / 2;
      frame_left_pre = fabsf(frame_left_pre);

      if (channel_ptr->peak_left_prefader < frame_left_pre)
      {
        channel_ptr->peak_left_prefader = frame_left_pre;
      }

      if (channel_ptr->peak_left_postfader < frame_left)
      {
        channel_ptr->peak_left_postfader = frame_left;
      }

      if (frame_left > channel_ptr->abspeak_postfader)
      {
        channel_ptr->abspeak_postfader = frame_left;
      }

      if (frame_left_pre > channel_ptr->abspeak_prefader)
      {
        channel_ptr->abspeak_prefader = frame_left_pre;
      }
    }

    /* Update input channel volume meter every so often */
    channel_ptr->peak_frames++;
    if (channel_ptr->peak_frames >= PEAK_FRAMES_CHUNK)
    {
      channel_ptr->meter_left_postfader = channel_ptr->peak_left_postfader;
      channel_ptr->peak_left_postfader = 0.0;
      channel_ptr->meter_left_prefader = channel_ptr->peak_left_prefader;
      channel_ptr->peak_left_prefader = 0.0;
      if (channel_ptr->stereo)
      {
        channel_ptr->meter_right_postfader = channel_ptr->peak_right_postfader;
        channel_ptr->peak_right_postfader = 0.0;
        channel_ptr->meter_right_prefader = channel_ptr->peak_right_prefader;
        channel_ptr->peak_right_prefader = 0.0;
      }

      channel_ptr->peak_frames = 0;
    }

    /* Finish off volume & balance level interpolation */
    channel_ptr->volume_idx++;
    if ((channel_ptr->volume != channel_ptr->volume_new) &&
     (channel_ptr->volume_idx >= steps)) {
      channel_ptr->volume = channel_ptr->volume_new;
      channel_ptr->volume_idx = 0;
    }
    channel_ptr->balance_idx++;
    if ((channel_ptr->balance != channel_ptr->balance_new) &&
     (channel_ptr->balance_idx >= steps)) {
      channel_ptr->balance = channel_ptr->balance_new;
      channel_ptr->balance_idx = 0;
    }
  }

  /* Calculate k-metering for input channel */
  if (channel_ptr->mixer_ptr->kmetering) {
    kmeter_process(&channel_ptr->kmeter_left, channel_ptr->frames_left, start, end);
    if (channel_ptr->stereo) {
      kmeter_process(&channel_ptr->kmeter_right, channel_ptr->frames_right, start, end);
    }
    kmeter_process(&channel_ptr->kmeter_prefader_left, channel_ptr->prefader_frames_left, start, end);
    if (channel_ptr->stereo)
      kmeter_process(&channel_ptr->kmeter_prefader_right, channel_ptr->prefader_frames_right, start, end);
    }
}

static inline void
mix(
  struct jack_mixer * mixer_ptr,
  jack_nframes_t start,         /* Index of first sample to process */
  jack_nframes_t end)           /* Index of sample to stop processing before */
{
  GSList *node_ptr;
  struct output_channel * output_channel_ptr;
  struct channel *channel_ptr;

  /* Calculate pre/post-fader output and peak values for each input channel */
  for (node_ptr = mixer_ptr->input_channels_list; node_ptr; node_ptr = g_slist_next(node_ptr))
  {
    channel_ptr = (struct channel*)node_ptr->data;
    calc_channel_frames(channel_ptr, start, end);
  }

  /* For all output channels: */
  for (node_ptr = mixer_ptr->output_channels_list; node_ptr; node_ptr = g_slist_next(node_ptr))
  {
    output_channel_ptr = node_ptr->data;
    channel_ptr = (struct channel*)output_channel_ptr;

    if (output_channel_ptr->system)
    {
      /* Don't bother mixing the channels if we are not connected */
      if (channel_ptr->stereo)
      {
        if (jack_port_connected(channel_ptr->port_left) == 0 &&
            jack_port_connected(channel_ptr->port_right) == 0)
          continue;
      }
      else {
        if (jack_port_connected(channel_ptr->port_left) == 0)
          continue;
      }
    }

    /* Mix this output channel */
    mix_one(output_channel_ptr, mixer_ptr->input_channels_list, start, end);
  }
}

static inline void
update_channel_buffers(
  struct channel * channel_ptr,
  jack_nframes_t nframes)
{
  channel_ptr->left_buffer_ptr = jack_port_get_buffer(channel_ptr->port_left, nframes);

  if (channel_ptr->stereo)
  {
    channel_ptr->right_buffer_ptr = jack_port_get_buffer(channel_ptr->port_right, nframes);
  }
}

static inline void
kmeter_calc_hold_fall(
  int *hold,
  float *fall,
  jack_nframes_t nframes,
  jack_nframes_t sr)
  {
    float t;
    t = (float) nframes / sr;
    *hold = (int)(0.5 / t + 0.5f);
    *fall = powf(10.0f, -0.05f * 10.5f * t);
  }

static inline void
set_kmeters_peak_params(
  struct channel *channel_ptr,
  jack_nframes_t nframes)
  {
    int hold;
    float fall;
    jack_nframes_t sr = jack_get_sample_rate(channel_ptr->mixer_ptr->jack_client);
    kmeter_calc_hold_fall(&hold, &fall, nframes, sr);
    channel_ptr->kmeter_left._hold = hold;
    channel_ptr->kmeter_right._hold = hold;
    channel_ptr->kmeter_left._fall = fall;
    channel_ptr->kmeter_right._fall = fall;
    channel_ptr->kmeter_prefader_left._hold = hold;
    channel_ptr->kmeter_prefader_right._hold = hold;
    channel_ptr->kmeter_prefader_left._fall = fall;
    channel_ptr->kmeter_prefader_right._fall = fall;
  }

static int jack_buffer_size_cb(jack_nframes_t nframes, void *arg) {
    struct jack_mixer *mixer_ptr  = (struct jack_mixer *) arg;
    struct channel *channel_ptr;
    GSList *list_ptr;
    /* Get input ports buffer pointers */
    for (list_ptr = mixer_ptr->input_channels_list; list_ptr; list_ptr = g_slist_next(list_ptr))
    {
      channel_ptr = list_ptr->data;
      set_kmeters_peak_params(channel_ptr, nframes);
    }

    /* Get output ports buffer pointer */
    for (list_ptr = mixer_ptr->output_channels_list; list_ptr; list_ptr = g_slist_next(list_ptr))
    {
      channel_ptr = list_ptr->data;
      set_kmeters_peak_params(channel_ptr, nframes);
    }
    return 0;
}

#define mixer_ptr ((struct jack_mixer *)context)

static int
process(
  jack_nframes_t nframes,
  void * context)
{
  GSList *node_ptr;
  struct channel * channel_ptr;
#if defined(HAVE_JACK_MIDI)
  jack_nframes_t i;
  jack_nframes_t event_count;
  jack_midi_event_t in_event;
  unsigned char* midi_out_buffer;
  void * midi_buffer;
  double volume, balance;
  uint8_t cc_channel_index;
  uint8_t cc_num, cc_val, cur_cc_val;
#endif

  /* Get input ports buffer pointers */
  for (node_ptr = mixer_ptr->input_channels_list; node_ptr; node_ptr = g_slist_next(node_ptr))
  {
    channel_ptr = node_ptr->data;
    update_channel_buffers(channel_ptr, nframes);
  }

  /* Get output ports buffer pointer */
  for (node_ptr = mixer_ptr->output_channels_list; node_ptr; node_ptr = g_slist_next(node_ptr))
  {
    channel_ptr = node_ptr->data;
    update_channel_buffers(channel_ptr, nframes);
  }

#if defined(HAVE_JACK_MIDI)
  midi_buffer = jack_port_get_buffer(mixer_ptr->port_midi_in, nframes);
  event_count = jack_midi_get_event_count(midi_buffer);

  for (i = 0 ; i < event_count; i++)
  {
    jack_midi_event_get(&in_event, midi_buffer, i);

    if (in_event.size != 3 ||
        (in_event.buffer[0] & 0xF0) != 0xB0 ||
        in_event.buffer[1] > 127 ||
        in_event.buffer[2] > 127)
    {
      continue;
    }

    assert(in_event.time < nframes);

    cc_num = (uint8_t)(in_event.buffer[1] & 0x7F);
    cc_val = (uint8_t)(in_event.buffer[2] & 0x7F);
    mixer_ptr->last_midi_cc = (int8_t)cc_num;

    LOG_DEBUG("%u: CC#%u -> %u\n", (unsigned int)(in_event.buffer[0]), cc_num, cc_val);

    /* Do we have a mapping for particular CC? */
    channel_ptr = mixer_ptr->midi_cc_map[cc_num];
    if (channel_ptr)
    {
      if (channel_ptr->midi_cc_balance_index == cc_num)
      {
        if (cc_val < 63) {
          balance = MAP(cc_val, 0.0, 63.0, -1.0, -0.015625);
        }
        else {
          balance = MAP(cc_val, 64.0, 127.0, 0.0, 1.0);
        }
        if (mixer_ptr->midi_behavior == Pick_Up &&
            !channel_ptr->midi_cc_balance_picked_up &&
            channel_balance_read(channel_ptr) - balance < BALANCE_PICKUP_THRESHOLD)
        {
          channel_set_midi_cc_balance_picked_up(channel_ptr, true);
        }
        if ((mixer_ptr->midi_behavior == Pick_Up &&
            channel_ptr->midi_cc_balance_picked_up) ||
            mixer_ptr->midi_behavior == Jump_To_Value)
        {
          channel_balance_write(channel_ptr, balance);

        }
      }
      else if (channel_ptr->midi_cc_volume_index == cc_num)
      {
        /* Is a MIDI scale set for corresponding channel? */
        if (channel_ptr->midi_scale) {
          volume = scale_scale_to_db(channel_ptr->midi_scale,
                                     (double)cc_val / 127);
          if (mixer_ptr->midi_behavior == Pick_Up &&
              !channel_ptr->midi_cc_volume_picked_up)
          {
              /* MIDI control in pick-up mode but not picked up yet */
              cur_cc_val = (uint8_t)(127 * scale_db_to_scale(
                channel_ptr->midi_scale,
                value_to_db(channel_ptr->volume)));
              if (cc_val == cur_cc_val)
              {
                /* Incoming MIDI CC value matches current volume level
                 * --> MIDI control is picked up
                 */
                channel_set_midi_cc_volume_picked_up(channel_ptr, true);
              }
          }
          if ((mixer_ptr->midi_behavior == Pick_Up &&
              channel_ptr->midi_cc_volume_picked_up) ||
              mixer_ptr->midi_behavior == Jump_To_Value)
          {
            channel_volume_write(channel_ptr, volume);
          }
        }
      }
      else if (channel_ptr->midi_cc_mute_index == cc_num)
      {
        if (cc_val >= 64) {
          channel_out_mute(channel_ptr);
        }
        else {
          channel_out_unmute(channel_ptr);
        }

      }
      else if (channel_ptr->midi_cc_solo_index == cc_num)
      {
        if (cc_val >= 64) {
            channel_solo(channel_ptr);
        }
        else {
            channel_unsolo(channel_ptr);
        }
      }
      channel_ptr->midi_in_got_events = true;
      if (channel_ptr->midi_change_callback) {
        channel_ptr->midi_change_callback(channel_ptr->midi_change_callback_data);
      }
    }

  }

  midi_buffer = jack_port_get_buffer(mixer_ptr->port_midi_out, nframes);
  jack_midi_clear_buffer(midi_buffer);

  for(i=0; i<nframes; i++)
  {
    for (cc_channel_index=0; cc_channel_index<128; cc_channel_index++)
    {
      channel_ptr = mixer_ptr->midi_cc_map[cc_channel_index];
      if (!channel_ptr)
      {
        continue;
      }
      if (!channel_ptr->midi_out_has_events)
      {
        continue;
      }
      if (channel_ptr->midi_out_has_events & CHANNEL_VOLUME && channel_ptr->midi_scale)
      {
          midi_out_buffer = jack_midi_event_reserve(midi_buffer, 0, 3);
          if (!midi_out_buffer)
            continue;

          midi_out_buffer[0] = 0xB0; /* control change */
          midi_out_buffer[1] = channel_ptr->midi_cc_volume_index;
          midi_out_buffer[2] = (unsigned char)(127 * scale_db_to_scale(channel_ptr->midi_scale,
                                               value_to_db(channel_ptr->volume_new)));

          LOG_DEBUG(
            "%u: CC#%u <- %u\n",
            (unsigned int)midi_out_buffer[0],
            (unsigned int)midi_out_buffer[1],
            (unsigned int)midi_out_buffer[2]);
      }
      if (channel_ptr->midi_out_has_events & CHANNEL_BALANCE)
      {
          midi_out_buffer = jack_midi_event_reserve(midi_buffer, 0, 3);
          if (!midi_out_buffer)
            continue;

          midi_out_buffer[0] = 0xB0; /* control change */
          midi_out_buffer[1] = channel_ptr->midi_cc_balance_index;
          balance = channel_balance_read(channel_ptr);
          if (balance < 0.0) {
            midi_out_buffer[2] = (unsigned char)(MAP(balance, -1.0, -0.015625, 0.0, 63.0) + 0.5);
          }
          else {
            midi_out_buffer[2] = (unsigned char)(MAP(balance, 0.0, 1.0, 64.0, 127.0) + 0.5);
          }

          LOG_DEBUG(
            "%u: CC#%u <- %u\n",
            (unsigned int)midi_out_buffer[0],
            (unsigned int)midi_out_buffer[1],
            (unsigned int)midi_out_buffer[2]);
      }
      if (channel_ptr->midi_out_has_events & CHANNEL_MUTE)
      {
          midi_out_buffer = jack_midi_event_reserve(midi_buffer, 0, 3);
          if (!midi_out_buffer)
            continue;

          midi_out_buffer[0] = 0xB0; /* control change */
          midi_out_buffer[1] = channel_ptr->midi_cc_mute_index;
          midi_out_buffer[2] = (unsigned char)(channel_is_out_muted(channel_ptr) ? 127 : 0);

          LOG_DEBUG(
            "%u: CC#%u <- %u\n",
            (unsigned int)midi_out_buffer[0],
            (unsigned int)midi_out_buffer[1],
            (unsigned int)midi_out_buffer[2]);
      }
      if (channel_ptr->midi_out_has_events & CHANNEL_SOLO)
      {
          midi_out_buffer = jack_midi_event_reserve(midi_buffer, 0, 3);
          if (!midi_out_buffer)
            continue;

          midi_out_buffer[0] = 0xB0; /* control change */
          midi_out_buffer[1] = channel_ptr->midi_cc_solo_index;
          midi_out_buffer[2] = (unsigned char)(channel_is_soloed(channel_ptr) ? 127 : 0);

          LOG_DEBUG(
            "%u: CC#%u <- %u\n",
            (unsigned int)midi_out_buffer[0],
            (unsigned int)midi_out_buffer[1],
            (unsigned int)midi_out_buffer[2]);
      }
      channel_ptr->midi_out_has_events = 0;
    }
  }

#endif

  mix(mixer_ptr, 0, nframes);

  return 0;
}

#undef mixer_ptr

jack_mixer_t
create(
  const char * jack_client_name_ptr,
  bool stereo)
{
  (void) stereo;
  int ret;
  struct jack_mixer * mixer_ptr;
  int i;
  char * localedir;

  localedir = getenv("LOCALEDIR");
  setlocale(LC_ALL, "");
  bindtextdomain("jack_mixer", localedir != NULL ? localedir : LOCALEDIR);
  textdomain("jack_mixer");

  mixer_ptr = malloc(sizeof(struct jack_mixer));
  if (mixer_ptr == NULL)
  {
    goto exit;
  }

  ret = pthread_mutex_init(&mixer_ptr->mutex, NULL);
  if (ret != 0)
  {
    goto exit_free;
  }

  mixer_ptr->input_channels_list = NULL;
  mixer_ptr->output_channels_list = NULL;

  mixer_ptr->soloed_channels = NULL;

  mixer_ptr->kmetering = true;

  mixer_ptr->last_midi_cc = -1;

  mixer_ptr->midi_behavior = Jump_To_Value;

  for (i = 0 ; i < 128 ; i++)
  {
    mixer_ptr->midi_cc_map[i] = NULL;
  }

  LOG_DEBUG("Initializing JACK.\n");
  mixer_ptr->jack_client = jack_client_open(jack_client_name_ptr, 0, NULL);
  if (mixer_ptr->jack_client == NULL)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_JACK_CLIENT_CREATE;
    goto exit_destroy_mutex;
  }

  LOG_DEBUG("JACK client created.\n");
  LOG_DEBUG("Sample rate: %u\n", jack_get_sample_rate(mixer_ptr->jack_client));


#if defined(HAVE_JACK_MIDI)
  mixer_ptr->port_midi_in = jack_port_register(mixer_ptr->jack_client, "midi in",
                                               JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
  if (mixer_ptr->port_midi_in == NULL)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_JACK_MIDI_IN_CREATE;
    goto close_jack;
  }

  mixer_ptr->port_midi_out = jack_port_register(mixer_ptr->jack_client, "midi out",
                                                JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
  if (mixer_ptr->port_midi_out == NULL)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_JACK_MIDI_OUT_CREATE;
    goto close_jack;
  }

#endif

  ret = jack_set_process_callback(mixer_ptr->jack_client, process, mixer_ptr);
  if (ret != 0)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_JACK_SET_PROCESS_CALLBACK;
    goto close_jack;
  }

  ret = jack_set_buffer_size_callback(mixer_ptr->jack_client, jack_buffer_size_cb, mixer_ptr);
  if (ret != 0)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_JACK_SET_BUFFER_SIZE_CALLBACK;
    goto close_jack;
  }

  ret = jack_activate(mixer_ptr->jack_client);
  if (ret != 0)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_JACK_ACTIVATE;
    goto close_jack;
  }

  return mixer_ptr;

close_jack:
  /* this should clear all other resources we obtained through the client handle */
  jack_client_close(mixer_ptr->jack_client);

exit_destroy_mutex:
  pthread_mutex_destroy(&mixer_ptr->mutex);

exit_free:
  free(mixer_ptr);

exit:
  return NULL;
}

#define mixer_ctx_ptr ((struct jack_mixer *)mixer)

void
destroy(
  jack_mixer_t mixer)
{
  LOG_DEBUG("Uninitializing JACK.\n");
  assert(mixer_ctx_ptr->jack_client != NULL);
  jack_client_close(mixer_ctx_ptr->jack_client);
  pthread_mutex_destroy(&mixer_ctx_ptr->mutex);
  free(mixer_ctx_ptr);
}


unsigned int
get_channels_count(
  jack_mixer_t mixer)
{
  return g_slist_length(mixer_ctx_ptr->input_channels_list);
}

const char*
get_client_name(
  jack_mixer_t mixer)
{
  return jack_get_client_name(mixer_ctx_ptr->jack_client);
}

bool
get_kmetering(
  jack_mixer_t mixer)
{
  return mixer_ctx_ptr->kmetering;
}

void
set_kmetering(
  jack_mixer_t mixer,
  bool flag)
{
  mixer_ctx_ptr->kmetering = flag;
}

int8_t
get_last_midi_cc(
  jack_mixer_t mixer)
{
  return mixer_ctx_ptr->last_midi_cc;
}

void
set_last_midi_cc(
  jack_mixer_t mixer,
  int8_t new_cc) {
  mixer_ctx_ptr->last_midi_cc = new_cc;
}

int
get_midi_behavior_mode(
  jack_mixer_t mixer)
{
  return mixer_ctx_ptr->midi_behavior;
}

void
set_midi_behavior_mode(
  jack_mixer_t mixer,
  enum midi_behavior_mode mode)
{
  mixer_ctx_ptr->midi_behavior = mode;
}

jack_mixer_channel_t
add_channel(
  jack_mixer_t mixer,
  const char * channel_name,
  bool stereo)
{
  struct channel * channel_ptr;
  char * port_name = NULL;
  size_t channel_name_size;

  channel_ptr = malloc(sizeof(struct channel));
  if (channel_ptr == NULL)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_CHANNEL_MALLOC;
    goto fail;
  }

  channel_ptr->mixer_ptr = mixer_ctx_ptr;

  channel_ptr->name = strdup(channel_name);
  if (channel_ptr->name == NULL)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_CHANNEL_NAME_MALLOC;
    goto fail_free_channel;
  }

  channel_name_size = strlen(channel_name);

  if (stereo)
  {
    port_name = malloc(channel_name_size + 3);
    if (port_name == NULL)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_CHANNEL_NAME_MALLOC;
      goto fail_free_channel_name;
    }

    memcpy(port_name, channel_name, channel_name_size);
    port_name[channel_name_size] = ' ';
    port_name[channel_name_size+1] = 'L';
    port_name[channel_name_size+2] = 0;

    channel_ptr->port_left = jack_port_register(channel_ptr->mixer_ptr->jack_client, port_name,
                                                JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    if (channel_ptr->port_left == NULL)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_PORT_REGISTER_LEFT;
      goto fail_free_port_name;
    }

    port_name[channel_name_size+1] = 'R';

    channel_ptr->port_right = jack_port_register(channel_ptr->mixer_ptr->jack_client, port_name,
                                                 JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    if (channel_ptr->port_right == NULL)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_PORT_REGISTER_RIGHT;
      goto fail_unregister_left_channel;
    }
  }
  else
  {
    channel_ptr->port_left = jack_port_register(channel_ptr->mixer_ptr->jack_client, channel_name,
                                                JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    if (channel_ptr->port_left == NULL)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_PORT_REGISTER;
      goto fail_free_channel_name;
    }
  }

  channel_ptr->stereo = stereo;

  int sr = jack_get_sample_rate(channel_ptr->mixer_ptr->jack_client);
  int fsize = jack_get_buffer_size(channel_ptr->mixer_ptr->jack_client);

  channel_ptr->volume_transition_seconds = VOLUME_TRANSITION_SECONDS;
  channel_ptr->num_volume_transition_steps = channel_ptr->volume_transition_seconds * sr + 1;
  channel_ptr->volume = 0.0;
  channel_ptr->volume_new = 0.0;
  channel_ptr->balance = 0.0;
  channel_ptr->balance_new = 0.0;
  channel_ptr->meter_left_prefader = channel_ptr->meter_left_postfader = -1.0;
  channel_ptr->meter_right_prefader = channel_ptr->meter_right_postfader = -1.0;
  channel_ptr->abspeak_postfader = 0.0;
  channel_ptr->abspeak_prefader = 0.0;
  channel_ptr->out_mute = false;

  kmeter_init(&channel_ptr->kmeter_left, fsize, sr);
  kmeter_init(&channel_ptr->kmeter_right, fsize, sr);
  kmeter_init(&channel_ptr->kmeter_prefader_left, fsize, sr);
  kmeter_init(&channel_ptr->kmeter_prefader_right, fsize, sr);

  channel_ptr->peak_left_prefader = channel_ptr->peak_left_postfader = 0.0;
  channel_ptr->peak_right_prefader = channel_ptr->peak_right_postfader = 0.0;
  channel_ptr->peak_frames = 0;

  channel_ptr->frames_left = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->frames_right = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->prefader_frames_left = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->prefader_frames_right = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));

  channel_ptr->NaN_detected = false;

  channel_ptr->midi_cc_volume_index = -1;
  channel_ptr->midi_cc_balance_index = -1;
  channel_ptr->midi_cc_mute_index = -1;
  channel_ptr->midi_cc_solo_index = -1;
  channel_ptr->midi_cc_volume_picked_up = false;
  channel_ptr->midi_cc_balance_picked_up = false;

  channel_ptr->midi_change_callback = NULL;
  channel_ptr->midi_change_callback_data = NULL;
  channel_ptr->midi_out_has_events = 0;

  channel_ptr->midi_scale = NULL;

  channel_ptr->mixer_ptr->input_channels_list = g_slist_prepend(
                  channel_ptr->mixer_ptr->input_channels_list, channel_ptr);

  free(port_name);
  return channel_ptr;

fail_unregister_left_channel:
  jack_port_unregister(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_left);

fail_free_port_name:
  free(port_name);

fail_free_channel_name:
  free(channel_ptr->name);

fail_free_channel:
  free(channel_ptr);
  channel_ptr = NULL;

fail:
  return NULL;
}

static jack_mixer_output_channel_t
create_output_channel(
  jack_mixer_t mixer,
  const char * channel_name,
  bool stereo,
  bool system)
{
  struct channel * channel_ptr;
  struct output_channel * output_channel_ptr;
  char * port_name = NULL;
  size_t channel_name_size;

  output_channel_ptr = malloc(sizeof(struct output_channel));
  channel_ptr = (struct channel*)output_channel_ptr;
  if (channel_ptr == NULL)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_CHANNEL_MALLOC;
    goto fail;
  }

  channel_ptr->mixer_ptr = mixer_ctx_ptr;

  channel_ptr->name = strdup(channel_name);
  if (channel_ptr->name == NULL)
  {
    _jack_mixer_error = JACK_MIXER_ERROR_CHANNEL_NAME_MALLOC;
    goto fail_free_channel;
  }

  if (stereo)
  {
    channel_name_size = strlen(channel_name);

    port_name = malloc(channel_name_size + 4);
    if (port_name == NULL)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_CHANNEL_NAME_MALLOC;
      goto fail_free_channel_name;
    }

    memcpy(port_name, channel_name, channel_name_size);
    port_name[channel_name_size] = ' ';
    port_name[channel_name_size+1] = 'L';
    port_name[channel_name_size+2] = 0;

    channel_ptr->port_left = jack_port_register(channel_ptr->mixer_ptr->jack_client, port_name,
                                                JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    if (channel_ptr->port_left == NULL)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_PORT_REGISTER_LEFT;
      goto fail_free_port_name;
    }

    port_name[channel_name_size+1] = 'R';

    channel_ptr->port_right = jack_port_register(channel_ptr->mixer_ptr->jack_client, port_name,
                                                 JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    if (channel_ptr->port_right == NULL)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_PORT_REGISTER_RIGHT;
      goto fail_unregister_left_channel;
    }
  }
  else
  {
    channel_ptr->port_left = jack_port_register(channel_ptr->mixer_ptr->jack_client, channel_name,
                                                JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    if (channel_ptr->port_left == NULL)
    {
      _jack_mixer_error = JACK_MIXER_ERROR_PORT_REGISTER;
      goto fail_free_channel_name;
    }
  }

  channel_ptr->stereo = stereo;
  channel_ptr->out_mute = false;

  int sr = jack_get_sample_rate(channel_ptr->mixer_ptr->jack_client);
  int fsize = jack_get_buffer_size(channel_ptr->mixer_ptr->jack_client);

  channel_ptr->volume_transition_seconds = VOLUME_TRANSITION_SECONDS;
  channel_ptr->num_volume_transition_steps =
    channel_ptr->volume_transition_seconds * sr + 1;
  channel_ptr->volume = 0.0;
  channel_ptr->volume_new = 0.0;
  channel_ptr->balance = 0.0;
  channel_ptr->balance_new = 0.0;
  channel_ptr->meter_left_prefader = channel_ptr->meter_left_postfader = -1.0;
  channel_ptr->meter_right_prefader = channel_ptr->meter_right_postfader = -1.0;
  channel_ptr->abspeak_postfader = 0.0;
  channel_ptr->abspeak_prefader = 0.0;
  kmeter_init(&channel_ptr->kmeter_left, fsize, sr);
  kmeter_init(&channel_ptr->kmeter_right, fsize, sr);
  kmeter_init(&channel_ptr->kmeter_prefader_left, fsize, sr);
  kmeter_init(&channel_ptr->kmeter_prefader_right, fsize, sr);

  channel_ptr->peak_left_prefader = channel_ptr->peak_left_postfader = 0.0;
  channel_ptr->peak_right_prefader = channel_ptr->peak_right_postfader = 0.0;
  channel_ptr->peak_frames = 0;

  channel_ptr->tmp_mixed_frames_left = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->tmp_mixed_frames_right = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->frames_left = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->frames_right = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->prefader_frames_left = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->prefader_frames_right = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));

  channel_ptr->NaN_detected = false;

  channel_ptr->midi_cc_volume_index = -1;
  channel_ptr->midi_cc_balance_index = -1;
  channel_ptr->midi_cc_mute_index = -1;
  channel_ptr->midi_cc_solo_index = -1;
  channel_ptr->midi_cc_volume_picked_up = false;
  channel_ptr->midi_cc_balance_picked_up = false;

  channel_ptr->midi_change_callback = NULL;
  channel_ptr->midi_change_callback_data = NULL;

  channel_ptr->midi_scale = NULL;

  output_channel_ptr->soloed_channels = NULL;
  output_channel_ptr->muted_channels = NULL;
  output_channel_ptr->prefader_channels = NULL;
  output_channel_ptr->system = system;
  output_channel_ptr->prefader = false;

  free(port_name);
  return output_channel_ptr;

fail_unregister_left_channel:
  jack_port_unregister(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_left);

fail_free_port_name:
  free(port_name);

fail_free_channel_name:
  free(channel_ptr->name);

fail_free_channel:
  free(channel_ptr);
  channel_ptr = NULL;

fail:
  return NULL;
}

jack_mixer_output_channel_t
add_output_channel(
  jack_mixer_t mixer,
  const char * channel_name,
  bool stereo,
  bool system)
{
  struct output_channel *output_channel_ptr;
  struct channel *channel_ptr;

  output_channel_ptr = create_output_channel(mixer, channel_name, stereo, system);
  if (output_channel_ptr == NULL) {
    return NULL;
  }
  channel_ptr = (struct channel*)output_channel_ptr;

  ((struct jack_mixer*)mixer)->output_channels_list = g_slist_prepend(
                  ((struct jack_mixer*)mixer)->output_channels_list, channel_ptr);

  return output_channel_ptr;
}

void
remove_channels(
  jack_mixer_t mixer)
{
  GSList *list_ptr;
  for (list_ptr = mixer_ctx_ptr->input_channels_list; list_ptr; list_ptr = g_slist_next(list_ptr))
  {
    struct channel *input_channel_ptr = list_ptr->data;
    remove_channel((jack_mixer_channel_t)input_channel_ptr);
  }
}

#define km ((struct kmeter *) kmeter)

void
kmeter_init(
  jack_mixer_kmeter_t kmeter,
  jack_nframes_t fsize,
  jack_nframes_t sr)
{
  km->_z1 = 0;
  km->_z2 = 0;
  km->_rms = 0;
  km->_dpk = 0;
  km->_cnt = 0;
  km->_flag = false;

  km->_omega = 9.72f / sr;
  kmeter_calc_hold_fall(&km->_hold, &km->_fall, fsize, sr);
}

void
kmeter_process(
  jack_mixer_kmeter_t kmeter,
  jack_default_audio_sample_t *p,
  int start,
  int end)
{
  int i;
  jack_default_audio_sample_t s, t, z1, z2;

  if (km->_flag) {
    km->_rms = 0;
    km->_flag = 0;
  }

  z1 = km->_z1;
  z2 = km->_z2;

  t = 0;

  for (i = start; i < end; i++) {
    s = p[i];
    s *= s;
    if (t < s) t = s;
    z1 += km->_omega * (s - z1);
    z2 += km->_omega * (z1 - z2);
  }
  t = sqrtf(t);

  km->_z1 = z1 + 1e-20f;
  km->_z2 = z2 + 1e-20f;

  s = sqrtf(2 * z2);
  if (s > km->_rms) km->_rms = s;

  if (t > km->_dpk) {
    km->_dpk = t;
    km->_cnt = km->_hold;
  }
  else if (km->_cnt) {
    km->_cnt--;
  }
  else {
    km->_dpk *= km->_fall;
    km->_dpk += 1e-10f;
  }
}

void
remove_output_channel(
  jack_mixer_output_channel_t output_channel)
{
  struct output_channel *output_channel_ptr = output_channel;
  struct channel *channel_ptr = output_channel;

  channel_ptr->mixer_ptr->output_channels_list = g_slist_remove(
                  channel_ptr->mixer_ptr->output_channels_list, channel_ptr);
  free(channel_ptr->name);

  jack_port_unregister(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_left);
  if (channel_ptr->stereo)
  {
    jack_port_unregister(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_right);
  }

  if (channel_ptr->midi_cc_volume_index != -1)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] = NULL;
  }

  if (channel_ptr->midi_cc_balance_index != -1)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] = NULL;
  }

  if (channel_ptr->midi_cc_mute_index != -1)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_mute_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_mute_index] = NULL;
  }

  if (channel_ptr->midi_cc_solo_index != -1)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_solo_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_solo_index] = NULL;
  }

  g_slist_free(output_channel_ptr->soloed_channels);
  g_slist_free(output_channel_ptr->muted_channels);
  g_slist_free(output_channel_ptr->prefader_channels);

  free(channel_ptr->tmp_mixed_frames_left);
  free(channel_ptr->tmp_mixed_frames_right);
  free(channel_ptr->frames_left);
  free(channel_ptr->frames_right);
  free(channel_ptr->prefader_frames_left);
  free(channel_ptr->prefader_frames_right);
  free(channel_ptr);
}

void
output_channel_set_solo(
  jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t channel,
  bool solo_value)
{
  struct output_channel *output_channel_ptr = output_channel;

  if (solo_value) {
    if (g_slist_find(output_channel_ptr->soloed_channels, channel) != NULL)
      return;
    output_channel_ptr->soloed_channels = g_slist_prepend(output_channel_ptr->soloed_channels, channel);
  }
  else {
    if (g_slist_find(output_channel_ptr->soloed_channels, channel) == NULL)
      return;
    output_channel_ptr->soloed_channels = g_slist_remove(output_channel_ptr->soloed_channels, channel);
  }
}

void
output_channel_set_muted(
  jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t channel,
  bool muted_value)
{
  struct output_channel *output_channel_ptr = output_channel;

  if (muted_value) {
    if (g_slist_find(output_channel_ptr->muted_channels, channel) != NULL)
      return;
    output_channel_ptr->muted_channels = g_slist_prepend(output_channel_ptr->muted_channels, channel);
  }
  else {
    if (g_slist_find(output_channel_ptr->muted_channels, channel) == NULL)
      return;
    output_channel_ptr->muted_channels = g_slist_remove(output_channel_ptr->muted_channels, channel);
  }
}

bool
output_channel_is_muted(
  jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t channel)
{
  struct output_channel *output_channel_ptr = output_channel;

  if (g_slist_find(output_channel_ptr->muted_channels, channel) != NULL)
    return true;
  return false;
}

bool
output_channel_is_solo(
  jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t channel)
{
  struct output_channel *output_channel_ptr = output_channel;

  if (g_slist_find(output_channel_ptr->soloed_channels, channel) != NULL)
    return true;
  return false;
}

void
output_channel_set_prefader(
  jack_mixer_output_channel_t output_channel,
  bool pfl_value)
{
  struct output_channel *output_channel_ptr = output_channel;
  output_channel_ptr->prefader = pfl_value;
}

bool
output_channel_is_prefader(
  jack_mixer_output_channel_t output_channel)
{
  struct output_channel *output_channel_ptr = output_channel;
  return output_channel_ptr->prefader;
}

void
output_channel_set_in_prefader(
  jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t channel,
  bool prefader_value)
{
  struct output_channel *output_channel_ptr = output_channel;

  if (prefader_value) {
    if (g_slist_find(output_channel_ptr->prefader_channels, channel) != NULL)
      return;
    output_channel_ptr->prefader_channels = g_slist_prepend(output_channel_ptr->prefader_channels, channel);
  }
  else {
    if (g_slist_find(output_channel_ptr->prefader_channels, channel) == NULL)
      return;
    output_channel_ptr->prefader_channels = g_slist_remove(output_channel_ptr->prefader_channels, channel);
  }
}

bool
output_channel_is_in_prefader(
  jack_mixer_output_channel_t output_channel,
  jack_mixer_channel_t channel)
{
  struct output_channel *output_channel_ptr = output_channel;

  if (g_slist_find(output_channel_ptr->prefader_channels, channel) != NULL)
    return true;
  return false;
}
