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

#include "config.h"

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <math.h>
#include <jack/jack.h>
#if defined(HAVE_JACK_MIDI)
#include <jack/midiport.h>
#endif
#include <assert.h>
#include <pthread.h>

#include <glib.h>

#include "jack_mixer.h"
//#define LOG_LEVEL LOG_LEVEL_DEBUG
#include "log.h"

#include "jack_compat.h"

#define PEAK_FRAMES_CHUNK 4800

// we don't know how much to allocate, but we don't want to wait with 
// allocating until we're in the process() callback, so we just take a 
// fairly big chunk: 4 periods per buffer, 4096 samples per period.
// (not sure if the '*4' is needed)
#define MAX_BLOCK_SIZE (4 * 4096)

#define FLOAT_EXISTS(x) (!((x) - (x)))

struct channel
{
  struct jack_mixer * mixer_ptr;
  char * name;
  bool stereo;
  float volume;
  float balance;
  float volume_left;
  float volume_right;
  float meter_left;
  float meter_right;
  float abspeak;
  jack_port_t * port_left;
  jack_port_t * port_right;

  jack_nframes_t peak_frames;
  float peak_left;
  float peak_right;

  jack_default_audio_sample_t * frames_left;
  jack_default_audio_sample_t * frames_right;
  jack_default_audio_sample_t * prefader_frames_left;
  jack_default_audio_sample_t * prefader_frames_right;

  bool NaN_detected;

  int midi_cc_volume_index;
  int midi_cc_balance_index;

  jack_default_audio_sample_t * left_buffer_ptr;
  jack_default_audio_sample_t * right_buffer_ptr;

  bool midi_in_got_events;
  void (*midi_change_callback) (void*);
  void *midi_change_callback_data;

  jack_mixer_scale_t midi_scale;
};

struct output_channel {
  struct channel channel;
  GSList *soloed_channels;
  GSList *muted_channels;
  bool system; /* system channel, without any associated UI */
  bool prefader;
};

struct jack_mixer
{
  pthread_mutex_t mutex;
  jack_client_t * jack_client;
  GSList *input_channels_list;
  GSList *output_channels_list;
  struct output_channel *main_mix_channel;

  jack_port_t * port_midi_in;
  jack_port_t * port_midi_out;
  unsigned int last_midi_channel;

  struct channel* midi_cc_map[128];
};

static jack_mixer_output_channel_t create_output_channel(
  jack_mixer_t mixer,
  const char * channel_name,
  bool stereo,
  bool system);

static inline void
update_channel_buffers(
  struct channel * channel_ptr,
  jack_nframes_t nframes);


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
  return powf(10.0, db/20.0);
}

void
calc_channel_volumes(
  struct channel * channel_ptr)
{
  if (channel_ptr->stereo)
  {
    if (channel_ptr->balance > 0)
    {
      channel_ptr->volume_left = channel_ptr->volume * (1 - channel_ptr->balance);
      channel_ptr->volume_right = channel_ptr->volume;
    }
    else
    {
      channel_ptr->volume_left = channel_ptr->volume;
      channel_ptr->volume_right = channel_ptr->volume * (1 + channel_ptr->balance);
    }
  }
  else
  {
    channel_ptr->volume_left = channel_ptr->volume * (1 - channel_ptr->balance);
    channel_ptr->volume_right = channel_ptr->volume * (1 + channel_ptr->balance);
  }
}

void
calc_all_channel_volumes(
  struct jack_mixer * mixer_ptr)
{
  struct channel * channel_ptr;
  GSList *list_ptr;

  for (list_ptr = mixer_ptr->input_channels_list; list_ptr; list_ptr = g_slist_next(list_ptr))
  {
    channel_ptr = list_ptr->data;
    calc_channel_volumes(channel_ptr);
  }
}

#define channel_ptr ((struct channel *)channel)

const char*
channel_get_name(
  jack_mixer_channel_t channel)
{
  return channel_ptr->name;
}

void
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
    return;
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

    ret = jack_port_set_name(channel_ptr->port_left, port_name);
    if (ret != 0)
    {
      /* what could we do here? */
    }

    port_name[channel_name_size+1] = 'R';

    ret = jack_port_set_name(channel_ptr->port_right, port_name);
    if (ret != 0)
    {
      /* what could we do here? */
    }

    free(port_name);
  }
  else
  {
    ret = jack_port_set_name(channel_ptr->port_left, name);
    if (ret != 0)
    {
      /* what could we do here? */
    }
  }
}

bool
channel_is_stereo(
  jack_mixer_channel_t channel)
{
  return channel_ptr->stereo;
}

unsigned int
channel_get_balance_midi_cc(
  jack_mixer_channel_t channel)
{
  return channel_ptr->midi_cc_balance_index;
}

unsigned int
channel_set_balance_midi_cc(
  jack_mixer_channel_t channel,
  unsigned int new_cc)
{
  if (new_cc > 127) {
    return 2; /* error: over limit CC */
  }
  if (channel_ptr->midi_cc_balance_index == new_cc) {
    /* no change */
    return 0;
  }
  if (new_cc == 0) {
    /* 0 is special, it removes the link */
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] = NULL;
    channel_ptr->midi_cc_balance_index = 0;
  } else {
    if (channel_ptr->mixer_ptr->midi_cc_map[new_cc] != NULL) {
      return 1; /* error: cc in use */
    }
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] = NULL;
    channel_ptr->mixer_ptr->midi_cc_map[new_cc] = channel_ptr;
    channel_ptr->midi_cc_balance_index = new_cc;
  }
  return 0;
}

unsigned int
channel_get_volume_midi_cc(
  jack_mixer_channel_t channel)
{
  return channel_ptr->midi_cc_volume_index;
}

unsigned int
channel_set_volume_midi_cc(
  jack_mixer_channel_t channel, unsigned int new_cc)
{
  if (new_cc > 127) {
    return 2; /* error: over limit CC */
  }
  if (channel_ptr->midi_cc_volume_index == new_cc) {
    /* no change */
    return 0;
  }
  if (new_cc == 0) {
    /* 0 is special, it removes the link */
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] = NULL;
    channel_ptr->midi_cc_volume_index = 0;
  } else {
    if (channel_ptr->mixer_ptr->midi_cc_map[new_cc] != NULL) {
      return 1; /* error: cc in use */
    }
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] = NULL;
    channel_ptr->mixer_ptr->midi_cc_map[new_cc] = channel_ptr;
    channel_ptr->midi_cc_volume_index = new_cc;
  }
  return 0;
}

void
channel_autoset_midi_cc(
  jack_mixer_channel_t channel)
{
  struct jack_mixer *mixer_ptr;
  int i;

  mixer_ptr = channel_ptr->mixer_ptr;

  for (i = 11 ; i < 128 ; i++)
  {
    if (mixer_ptr->midi_cc_map[i] == NULL)
    {
      mixer_ptr->midi_cc_map[i] = channel_ptr;
      channel_ptr->midi_cc_volume_index = i;

      LOG_NOTICE("New channel \"%s\" volume mapped to CC#%i", channel_ptr->name, i);

      break;
    }
  }

  for (; i < 128 ; i++)
  {
    if (mixer_ptr->midi_cc_map[i] == NULL)
    {
      mixer_ptr->midi_cc_map[i] = channel_ptr;
      channel_ptr->midi_cc_balance_index = i;

      LOG_NOTICE("New channel \"%s\" balance mapped to CC#%i", channel_ptr->name, i);

      break;
    }
  }
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
  channel_unmute(channel_ptr);
  channel_unsolo(channel_ptr);
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

  if (channel_ptr->midi_cc_volume_index != 0)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] = NULL;
  }

  if (channel_ptr->midi_cc_balance_index != 0)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] = NULL;
  }

  free(channel_ptr);
}

void
channel_stereo_meter_read(
  jack_mixer_channel_t channel,
  double * left_ptr,
  double * right_ptr)
{
  assert(channel_ptr);
  *left_ptr = value_to_db(channel_ptr->meter_left);
  *right_ptr = value_to_db(channel_ptr->meter_right);
}

void
channel_mono_meter_read(
  jack_mixer_channel_t channel,
  double * mono_ptr)
{
  *mono_ptr = value_to_db(channel_ptr->meter_left);
}

void
channel_volume_write(
  jack_mixer_channel_t channel,
  double volume)
{
  assert(channel_ptr);
  channel_ptr->volume = db_to_value(volume);
  calc_channel_volumes(channel_ptr);
}

double
channel_volume_read(
  jack_mixer_channel_t channel)
{
  assert(channel_ptr);
  return value_to_db(channel_ptr->volume);
}

void
channel_balance_write(
  jack_mixer_channel_t channel,
  double balance)
{
  assert(channel_ptr);
  channel_ptr->balance = balance;
  calc_channel_volumes(channel_ptr);
}

double
channel_balance_read(
  jack_mixer_channel_t channel)
{
  assert(channel_ptr);
  return channel_ptr->balance;
}

double
channel_abspeak_read(
  jack_mixer_channel_t channel)
{
  assert(channel_ptr);
  if (channel_ptr->NaN_detected)
  {
    return sqrt(-1);
  }
  else
  {
    return value_to_db(channel_ptr->abspeak);
  }
}

void
channel_abspeak_reset(
  jack_mixer_channel_t channel)
{
  channel_ptr->abspeak = 0;
  channel_ptr->NaN_detected = false;
}

void
channel_mute(
  jack_mixer_channel_t channel)
{
  output_channel_set_muted(channel_ptr->mixer_ptr->main_mix_channel, channel, true);
}

void
channel_unmute(
  jack_mixer_channel_t channel)
{
  output_channel_set_muted(channel_ptr->mixer_ptr->main_mix_channel, channel, false);
}

void
channel_solo(
  jack_mixer_channel_t channel)
{
  output_channel_set_solo(channel_ptr->mixer_ptr->main_mix_channel, channel, true);
}

void
channel_unsolo(
  jack_mixer_channel_t channel)
{
  output_channel_set_solo(channel_ptr->mixer_ptr->main_mix_channel, channel, false);
}

bool
channel_is_muted(
  jack_mixer_channel_t channel)
{
  if (g_slist_find(channel_ptr->mixer_ptr->main_mix_channel->muted_channels, channel))
    return true;
  return false;
}

bool
channel_is_soloed(
  jack_mixer_channel_t channel)
{
  if (g_slist_find(channel_ptr->mixer_ptr->main_mix_channel->soloed_channels, channel))
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

/* process input channels and mix them into main mix */
static inline void
mix_one(
  struct output_channel *output_mix_channel,
  GSList *channels_list,
  jack_nframes_t start,         /* index of first sample to process */
  jack_nframes_t end)           /* index of sample to stop processing before */
{
  jack_nframes_t i;
  GSList *node_ptr;
  struct channel * channel_ptr;
  jack_default_audio_sample_t frame_left;
  jack_default_audio_sample_t frame_right;
  struct channel *mix_channel = (struct channel*)output_mix_channel;

  for (i = start; i < end; i++)
  {
    mix_channel->left_buffer_ptr[i] = 0.0;
    if (mix_channel->stereo)
      mix_channel->right_buffer_ptr[i] = 0.0;
  }


  for (node_ptr = channels_list; node_ptr; node_ptr = g_slist_next(node_ptr))
  {
    channel_ptr = node_ptr->data;

    if (g_slist_find(output_mix_channel->muted_channels, channel_ptr) != NULL) {
      /* skip muted channels */
      continue;
    }

    if (output_mix_channel->soloed_channels &&
        g_slist_find(output_mix_channel->soloed_channels, channel_ptr) == NULL) {
      /* skip channels that are not soloed, when some are */
      continue;
    }

    for (i = start ; i < end ; i++)
    {
      if (! output_mix_channel->prefader) {
        frame_left = channel_ptr->frames_left[i-start];
      } else {
        frame_left = channel_ptr->prefader_frames_left[i-start];
      }
      if (frame_left == NAN)
        break;
      mix_channel->left_buffer_ptr[i] += frame_left;

      if (mix_channel->stereo)
      {
        if (! output_mix_channel->prefader) {
          frame_right = channel_ptr->frames_right[i-start];
        } else {
          frame_right = channel_ptr->prefader_frames_right[i-start];
        }
        if (frame_right == NAN)
          break;

        mix_channel->right_buffer_ptr[i] += frame_right;
      }

    }

  }

  /* process main mix channel */
  for (i = start ; i < end ; i++)
  {
    if (! output_mix_channel->prefader) {
      mix_channel->left_buffer_ptr[i] *= mix_channel->volume_left;
      if (mix_channel->stereo)
      {
        mix_channel->right_buffer_ptr[i] *= mix_channel->volume_right;
      }
    }

    frame_left = fabsf(mix_channel->left_buffer_ptr[i]);
    if (mix_channel->peak_left < frame_left)
    {
      mix_channel->peak_left = frame_left;

      if (frame_left > mix_channel->abspeak)
      {
        mix_channel->abspeak = frame_left;
      }
    }

    if (mix_channel->stereo)
    {
      frame_right = fabsf(mix_channel->right_buffer_ptr[i]);
      if (mix_channel->peak_right < frame_right)
      {
        mix_channel->peak_right = frame_right;

        if (frame_right > mix_channel->abspeak)
        {
          mix_channel->abspeak = frame_right;
        }
      }
    }

    mix_channel->peak_frames++;
    if (mix_channel->peak_frames >= PEAK_FRAMES_CHUNK)
    {
      mix_channel->meter_left = mix_channel->peak_left;
      mix_channel->peak_left = 0.0;

      if (mix_channel->stereo)
      {
        mix_channel->meter_right = mix_channel->peak_right;
        mix_channel->peak_right = 0.0;
      }

      mix_channel->peak_frames = 0;
    }
  }
}

static inline void
calc_channel_frames(
  struct channel *channel_ptr,
  jack_nframes_t start,
  jack_nframes_t end)
{
  jack_nframes_t i;
  jack_default_audio_sample_t frame_left;
  jack_default_audio_sample_t frame_right;

  for (i = start ; i < end ; i++)
  {
    if (i-start >= MAX_BLOCK_SIZE)
    {
      fprintf(stderr, "i-start too high: %d - %d\n", i, start);
    }
    channel_ptr->prefader_frames_left[i-start] = channel_ptr->left_buffer_ptr[i];
    if (channel_ptr->stereo)
      channel_ptr->prefader_frames_right[i-start] = channel_ptr->right_buffer_ptr[i];

    if (!FLOAT_EXISTS(channel_ptr->left_buffer_ptr[i]))
    {
      channel_ptr->NaN_detected = true;
      channel_ptr->frames_left[i-start] = NAN;
      break;
    }

    frame_left = channel_ptr->left_buffer_ptr[i] * channel_ptr->volume_left;

    if (channel_ptr->stereo)
    {
      if (!FLOAT_EXISTS(channel_ptr->right_buffer_ptr[i]))
      {
        channel_ptr->NaN_detected = true;
        channel_ptr->frames_right[i-start] = NAN;
        break;
      }

      frame_right = channel_ptr->right_buffer_ptr[i] * channel_ptr->volume_right;
    }
    else
    {
      frame_right = channel_ptr->left_buffer_ptr[i] * channel_ptr->volume_right;
    }

    channel_ptr->frames_left[i-start] = frame_left;
    channel_ptr->frames_right[i-start] = frame_right;

    if (channel_ptr->stereo)
    {
      frame_left = fabsf(frame_left);
      frame_right = fabsf(frame_right);

      if (channel_ptr->peak_left < frame_left)
      {
        channel_ptr->peak_left = frame_left;

        if (frame_left > channel_ptr->abspeak)
        {
          channel_ptr->abspeak = frame_left;
        }
      }

      if (channel_ptr->peak_right < frame_right)
      {
        channel_ptr->peak_right = frame_right;

        if (frame_right > channel_ptr->abspeak)
        {
          channel_ptr->abspeak = frame_right;
        }
      }
    }
    else
    {
      frame_left = (fabsf(frame_left) + fabsf(frame_right)) / 2;

      if (channel_ptr->peak_left < frame_left)
      {
        channel_ptr->peak_left = frame_left;

        if (frame_left > channel_ptr->abspeak)
        {
          channel_ptr->abspeak = frame_left;
        }
      }
    }

    channel_ptr->peak_frames++;
    if (channel_ptr->peak_frames >= PEAK_FRAMES_CHUNK)
    {
      channel_ptr->meter_left = channel_ptr->peak_left;
      channel_ptr->peak_left = 0.0;

      if (channel_ptr->stereo)
      {
        channel_ptr->meter_right = channel_ptr->peak_right;
        channel_ptr->peak_right = 0.0;
      }

      channel_ptr->peak_frames = 0;
    }
  }

}

static inline void
mix(
  struct jack_mixer * mixer_ptr,
  jack_nframes_t start,         /* index of first sample to process */
  jack_nframes_t end)           /* index of sample to stop processing before */
{
  GSList *node_ptr;
  struct output_channel * output_channel_ptr;
  struct channel *channel_ptr;

  for (node_ptr = mixer_ptr->input_channels_list; node_ptr; node_ptr = g_slist_next(node_ptr))
  {
    channel_ptr = (struct channel*)node_ptr->data;
    calc_channel_frames(channel_ptr, start, end);
  }

  mix_one((struct output_channel*)mixer_ptr->main_mix_channel, mixer_ptr->input_channels_list, start, end);

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
      } else {
         if (jack_port_connected(channel_ptr->port_left) == 0)
           continue;
      }
    }

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

#define mixer_ptr ((struct jack_mixer *)context)

static int
process(
  jack_nframes_t nframes,
  void * context)
{
  jack_nframes_t i;
  GSList *node_ptr;
  struct channel * channel_ptr;
#if defined(HAVE_JACK_MIDI)
  jack_nframes_t event_count;
  jack_midi_event_t in_event;
  void * midi_buffer;
  signed char byte;
#endif
  jack_nframes_t offset;

  for (node_ptr = mixer_ptr->input_channels_list; node_ptr; node_ptr = g_slist_next(node_ptr))
  {
    channel_ptr = node_ptr->data;
    update_channel_buffers(channel_ptr, nframes);
  }

  // Fill output buffers with the input 
  update_channel_buffers((struct channel*)mixer_ptr->main_mix_channel, nframes);
  for (node_ptr = mixer_ptr->output_channels_list; node_ptr; node_ptr = g_slist_next(node_ptr))
  {
    channel_ptr = node_ptr->data;
    update_channel_buffers(channel_ptr, nframes);
  }

  offset = 0;

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

    LOG_DEBUG(
      "%u: CC#%u -> %u",
      (unsigned int)(in_event.buffer[0] & 0x0F),
      (unsigned int)in_event.buffer[1],
      (unsigned int)in_event.buffer[2]);

    mixer_ptr->last_midi_channel = (unsigned int)in_event.buffer[1];
    channel_ptr = mixer_ptr->midi_cc_map[in_event.buffer[1]];

    /* if we have mapping for particular CC and MIDI scale is set for corresponding channel */
    if (channel_ptr != NULL && channel_ptr->midi_scale != NULL)
    {
      assert(in_event.time >= offset);

      if (in_event.time > offset)
      {
        // Perform the mixing of the part between the previous volume change
        // (or the start of the block) up until this one.
        mix(mixer_ptr, offset, in_event.time);
        offset = in_event.time;
      }

      if (channel_ptr->midi_cc_balance_index == (unsigned int)in_event.buffer[1])
      {
        byte = in_event.buffer[2];
        if (byte == 0)
        {
          byte = 1;
        }
        byte -= 64;

        channel_ptr->balance = (float)byte / 63;
        LOG_DEBUG("\"%s\" balance -> %f", channel_ptr->name, channel_ptr->balance);
      }
      else
      {
        channel_ptr->volume = db_to_value(scale_scale_to_db(channel_ptr->midi_scale, (double)in_event.buffer[2] / 127));
        LOG_DEBUG("\"%s\" volume -> %f", channel_ptr->name, channel_ptr->volume);
      }

      calc_channel_volumes(channel_ptr);

      channel_ptr->midi_in_got_events = true;
      if (channel_ptr->midi_change_callback)
        channel_ptr->midi_change_callback(channel_ptr->midi_change_callback_data);

    }

  }

#endif

  mix(mixer_ptr, offset, nframes);

  return 0;
}

#undef mixer_ptr

jack_mixer_t
create(
  const char * jack_client_name_ptr)
{
  int ret;
  struct jack_mixer * mixer_ptr;
  int i;


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

  mixer_ptr->last_midi_channel = 0;

  for (i = 0 ; i < 128 ; i++)
  {
    mixer_ptr->midi_cc_map[i] = NULL;
  }

  LOG_DEBUG("Initializing JACK");
  mixer_ptr->jack_client = jack_client_open(jack_client_name_ptr, 0, NULL);
  if (mixer_ptr->jack_client == NULL)
  {
    LOG_ERROR("Cannot create JACK client.");
    LOG_NOTICE("Please make sure JACK daemon is running.");
    goto exit_destroy_mutex;
  }

  LOG_DEBUG("JACK client created");

  LOG_DEBUG("Sample rate: %" PRIu32, jack_get_sample_rate(mixer_ptr->jack_client));

  mixer_ptr->main_mix_channel = create_output_channel(mixer_ptr, "MAIN", true, false);
  if (mixer_ptr->main_mix_channel == NULL) {
    LOG_ERROR("Cannot create main mix channel");
    goto close_jack;
  }
  channel_set_volume_midi_cc(mixer_ptr->main_mix_channel, 7);
  channel_set_balance_midi_cc(mixer_ptr->main_mix_channel, 8);

  ((struct channel*)(mixer_ptr->main_mix_channel))->mixer_ptr = mixer_ptr;

#if defined(HAVE_JACK_MIDI)
  mixer_ptr->port_midi_in = jack_port_register(mixer_ptr->jack_client, "midi in", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
  if (mixer_ptr->port_midi_in == NULL)
  {
    LOG_ERROR("Cannot create JACK MIDI in port");
    goto close_jack;
  }

  mixer_ptr->port_midi_out = jack_port_register(mixer_ptr->jack_client, "midi out", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
  if (mixer_ptr->port_midi_out == NULL)
  {
    LOG_ERROR("Cannot create JACK MIDI out port");
    goto close_jack;
  }

#endif

  calc_channel_volumes((struct channel*)mixer_ptr->main_mix_channel);

  ret = jack_set_process_callback(mixer_ptr->jack_client, process, mixer_ptr);
  if (ret != 0)
  {
    LOG_ERROR("Cannot set JACK process callback");
    goto close_jack;
  }

  ret = jack_activate(mixer_ptr->jack_client);
  if (ret != 0)
  {
    LOG_ERROR("Cannot activate JACK client");
    goto close_jack;
  }

  return mixer_ptr;

close_jack:
  jack_client_close(mixer_ptr->jack_client); /* this should clear all other resources we obtained through the client handle */

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
  LOG_DEBUG("Uninitializing JACK");

  assert(mixer_ctx_ptr->jack_client != NULL);

  jack_client_close(mixer_ctx_ptr->jack_client);

  pthread_mutex_destroy(&mixer_ctx_ptr->mutex);

  free(mixer_ctx_ptr->main_mix_channel);
  free(mixer_ctx_ptr);
}

jack_mixer_channel_t
get_main_mix_channel(
  jack_mixer_t mixer)
{
  return (struct channel*)mixer_ctx_ptr->main_mix_channel;
}

unsigned int
get_channels_count(
  jack_mixer_t mixer)
{
  return g_slist_length(mixer_ctx_ptr->input_channels_list);
}

unsigned int
get_last_midi_channel(
  jack_mixer_t mixer)
{
  return mixer_ctx_ptr->last_midi_channel;
}

jack_mixer_channel_t
add_channel(
  jack_mixer_t mixer,
  const char * channel_name,
  bool stereo)
{
  struct channel * channel_ptr;
  char * port_name;
  size_t channel_name_size;

  channel_ptr = malloc(sizeof(struct channel));
  if (channel_ptr == NULL)
  {
    goto fail;
  }

  channel_ptr->mixer_ptr = mixer_ctx_ptr;

  channel_ptr->name = strdup(channel_name);
  if (channel_ptr->name == NULL)
  {
    goto fail_free_channel;
  }

  channel_name_size = strlen(channel_name);

  if (stereo)
  {
    port_name = malloc(channel_name_size + 3);
    if (port_name == NULL)
    {
        goto fail_free_channel_name;
    }

    memcpy(port_name, channel_name, channel_name_size);
    port_name[channel_name_size] = ' ';
    port_name[channel_name_size+1] = 'L';
    port_name[channel_name_size+2] = 0;

    channel_ptr->port_left = jack_port_register(channel_ptr->mixer_ptr->jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    if (channel_ptr->port_left == NULL)
    {
        goto fail_free_port_name;
    }

    port_name[channel_name_size+1] = 'R';

    channel_ptr->port_right = jack_port_register(channel_ptr->mixer_ptr->jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    if (channel_ptr->port_right == NULL)
    {
        goto fail_unregister_left_channel;
    }
  }
  else
  {
    channel_ptr->port_left = jack_port_register(channel_ptr->mixer_ptr->jack_client, channel_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    if (channel_ptr->port_left == NULL)
    {
        goto fail_free_channel_name;
    }
  }

  channel_ptr->stereo = stereo;

  channel_ptr->volume = 0.0;
  channel_ptr->balance = 0.0;
  channel_ptr->meter_left = -1.0;
  channel_ptr->meter_right = -1.0;
  channel_ptr->abspeak = 0.0;

  channel_ptr->peak_left = 0.0;
  channel_ptr->peak_right = 0.0;
  channel_ptr->peak_frames = 0;

  channel_ptr->frames_left = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->frames_right = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->prefader_frames_left = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->prefader_frames_right = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));

  channel_ptr->NaN_detected = false;

  channel_ptr->midi_cc_volume_index = 0;
  channel_ptr->midi_cc_balance_index = 0;
  channel_ptr->midi_change_callback = NULL;
  channel_ptr->midi_change_callback_data = NULL;

  channel_ptr->midi_scale = NULL;

  calc_channel_volumes(channel_ptr);

  channel_ptr->mixer_ptr->input_channels_list = g_slist_prepend(
                  channel_ptr->mixer_ptr->input_channels_list, channel_ptr);

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
  char * port_name;
  size_t channel_name_size;

  output_channel_ptr = malloc(sizeof(struct output_channel));
  channel_ptr = (struct channel*)output_channel_ptr;
  if (channel_ptr == NULL)
  {
    goto fail;
  }

  channel_ptr->mixer_ptr = mixer_ctx_ptr;

  channel_ptr->name = strdup(channel_name);
  if (channel_ptr->name == NULL)
  {
    goto fail_free_channel;
  }

  if (stereo)
  {
    channel_name_size = strlen(channel_name);

    port_name = malloc(channel_name_size + 4);
    if (port_name == NULL)
    {
        goto fail_free_channel_name;
    }

    memcpy(port_name, channel_name, channel_name_size);
    port_name[channel_name_size] = ' ';
    port_name[channel_name_size+1] = 'L';
    port_name[channel_name_size+2] = 0;

    channel_ptr->port_left = jack_port_register(channel_ptr->mixer_ptr->jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    if (channel_ptr->port_left == NULL)
    {
        goto fail_free_port_name;
    }

    port_name[channel_name_size+1] = 'R';

    channel_ptr->port_right = jack_port_register(channel_ptr->mixer_ptr->jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    if (channel_ptr->port_right == NULL)
    {
        goto fail_unregister_left_channel;
    }
  }
  else
  {
    channel_ptr->port_left = jack_port_register(channel_ptr->mixer_ptr->jack_client, channel_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    if (channel_ptr->port_left == NULL)
    {
        goto fail_free_channel_name;
    }
  }

  channel_ptr->stereo = stereo;

  channel_ptr->volume = 0.0;
  channel_ptr->balance = 0.0;
  channel_ptr->meter_left = -1.0;
  channel_ptr->meter_right = -1.0;
  channel_ptr->abspeak = 0.0;

  channel_ptr->peak_left = 0.0;
  channel_ptr->peak_right = 0.0;
  channel_ptr->peak_frames = 0;

  channel_ptr->frames_left = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->frames_right = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->prefader_frames_left = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));
  channel_ptr->prefader_frames_right = calloc(MAX_BLOCK_SIZE, sizeof(jack_default_audio_sample_t));

  channel_ptr->NaN_detected = false;

  channel_ptr->midi_cc_volume_index = 0;
  channel_ptr->midi_cc_balance_index = 0;
  channel_ptr->midi_change_callback = NULL;
  channel_ptr->midi_change_callback_data = NULL;

  channel_ptr->midi_scale = NULL;

  output_channel_ptr->soloed_channels = NULL;
  output_channel_ptr->muted_channels = NULL;
  output_channel_ptr->system = system;
  output_channel_ptr->prefader = false;

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

  if (channel_ptr->midi_cc_volume_index != 0)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_volume_index] = NULL;
  }

  if (channel_ptr->midi_cc_balance_index != 0)
  {
    assert(channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] == channel_ptr);
    channel_ptr->mixer_ptr->midi_cc_map[channel_ptr->midi_cc_balance_index] = NULL;
  }

  g_slist_free(output_channel_ptr->soloed_channels);
  g_slist_free(output_channel_ptr->muted_channels);

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
  } else {
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
  } else {
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
