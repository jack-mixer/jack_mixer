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

#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <math.h>
#include <jack/jack.h>
#include <jack/midiport.h>
#include <assert.h>

#include "jack_mixer.h"
#include "list.h"
//#define LOG_LEVEL LOG_LEVEL_DEBUG
#include "log.h"

#define PEAK_FRAMES_CHUNK 4800

#define FLOAT_EXISTS(x) (!((x) - (x)))

struct channel
{
  struct list_head siblings;
  struct jack_mixer * mixer_ptr;
  char * name;
  bool stereo;
  float volume;
  float balance;
  bool muted;
  bool soloed;
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

  bool NaN_detected;

  struct channel ** cc_map_volume_ptr_ptr;
  struct channel ** cc_map_balance_ptr_ptr;
};

struct jack_mixer
{
  jack_client_t * jack_client;
  struct list_head channels_list;
  struct channel main_mix_channel;
  unsigned int channels_count;
  unsigned int soloed_channels_count;

  jack_port_t * port_midi_in;
  jack_port_t * port_midi_out;

  struct
  {
    bool balance;               /* volume or balance is controlled by this mapping */
    struct channel * channel_ptr;
  } midi_cc_map[128];
};

float value_to_db(float value)
{
  if (value <= 0)
  {
    return -INFINITY;
  }

  return 20.0 * log10f(value);
}

float db_to_value(float db)
{
  return powf(10.0, db/20.0);
}

void
calc_channel_volumes(struct channel * channel_ptr)
{
  if (channel_ptr->muted)
  {
    channel_ptr->volume_left = 0;
    channel_ptr->volume_right = 0;
    return;
  }

  if (channel_ptr->mixer_ptr->soloed_channels_count > 0 && !channel_ptr->soloed) /* there are soloed channels but we are not one of them */
  {
    channel_ptr->volume_left = 0;
    channel_ptr->volume_right = 0;
    return;
  }

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
  struct list_head * node_ptr;
  struct channel * channel_ptr;

  list_for_each(node_ptr, &mixer_ptr->channels_list)
  {
    channel_ptr = list_entry(node_ptr, struct channel, siblings);
    calc_channel_volumes(channel_ptr);
  }
}

#define channel_ptr ((struct channel *)channel)

const char * channel_get_name(jack_mixer_channel_t channel)
{
  return channel_ptr->name;
}

void channel_rename(jack_mixer_channel_t channel, const char * name)
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

bool channel_is_stereo(jack_mixer_channel_t channel)
{
  return channel_ptr->stereo;
}

void remove_channel(jack_mixer_channel_t channel)
{
  list_del(&channel_ptr->siblings);
  free(channel_ptr->name);

  jack_port_unregister(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_left);
  if (channel_ptr->stereo)
  {
    jack_port_unregister(channel_ptr->mixer_ptr->jack_client, channel_ptr->port_right);
  }

  channel_ptr->mixer_ptr->channels_count--;

  if (channel_ptr->cc_map_volume_ptr_ptr != NULL)
  {
    assert(*(channel_ptr->cc_map_volume_ptr_ptr) == channel_ptr);
    *(channel_ptr->cc_map_volume_ptr_ptr) = NULL;
  }

  if (channel_ptr->cc_map_balance_ptr_ptr != NULL)
  {
    assert(*(channel_ptr->cc_map_balance_ptr_ptr) == channel_ptr);
    *(channel_ptr->cc_map_balance_ptr_ptr) = NULL;
  }

  free(channel_ptr);
}

void channel_stereo_meter_read(jack_mixer_channel_t channel, double * left_ptr, double * right_ptr)
{
  *left_ptr = value_to_db(channel_ptr->meter_left);
  *right_ptr = value_to_db(channel_ptr->meter_right);
}

void channel_mono_meter_read(jack_mixer_channel_t channel, double * mono_ptr)
{
  *mono_ptr = value_to_db(channel_ptr->meter_left);
}

void channel_volume_write(jack_mixer_channel_t channel, double volume)
{
  channel_ptr->volume = db_to_value(volume);
  calc_channel_volumes(channel_ptr);
}

void channel_balance_write(jack_mixer_channel_t channel, double balance)
{
  channel_ptr->balance = balance;
  calc_channel_volumes(channel_ptr);
}

double channel_abspeak_read(jack_mixer_channel_t channel)
{
  if (channel_ptr->NaN_detected)
  {
    return sqrt(-1);
  }
  else
  {
    return value_to_db(channel_ptr->abspeak);
  }
}

void channel_abspeak_reset(jack_mixer_channel_t channel)
{
  channel_ptr->abspeak = 0;
  channel_ptr->NaN_detected = false;
}

void channel_mute(jack_mixer_channel_t channel)
{
  channel_ptr->muted = true;
  calc_channel_volumes(channel_ptr);
}

void channel_unmute(jack_mixer_channel_t channel)
{
  channel_ptr->muted = false;
  calc_channel_volumes(channel_ptr);
}

void channel_solo(jack_mixer_channel_t channel)
{
  if (!channel_ptr->soloed)
  {
    channel_ptr->soloed = true;
    channel_ptr->mixer_ptr->soloed_channels_count++;

    if (channel_ptr->mixer_ptr->soloed_channels_count == 1)
    {
      calc_all_channel_volumes(channel_ptr->mixer_ptr);
    }
    else
    {
      calc_channel_volumes(channel_ptr);
    }
  }
}

void channel_unsolo(jack_mixer_channel_t channel)
{
  if (channel_ptr->soloed)
  {
    channel_ptr->soloed = false;
    channel_ptr->mixer_ptr->soloed_channels_count--;

    if (channel_ptr->mixer_ptr->soloed_channels_count == 0)
    {
      calc_all_channel_volumes(channel_ptr->mixer_ptr);
    }
    else
    {
      calc_channel_volumes(channel_ptr);
    }
  }
}

bool channel_is_muted(jack_mixer_channel_t channel)
{
  return channel_ptr->muted;
}

bool channel_is_soloed(jack_mixer_channel_t channel)
{
  return channel_ptr->soloed;
}

#undef channel_ptr

#define mixer_ptr ((struct jack_mixer *)context)

int
process(jack_nframes_t nframes, void * context)
{
  jack_default_audio_sample_t * out_left;
  jack_default_audio_sample_t * out_right;
  jack_default_audio_sample_t * in_left;
  jack_default_audio_sample_t * in_right;
  jack_nframes_t i;
  struct list_head * node_ptr;
  struct channel * channel_ptr;
  jack_default_audio_sample_t frame_left;
  jack_default_audio_sample_t frame_right;
  jack_nframes_t event_count;
  jack_midi_event_t in_event;
  void * midi_buffer;

  out_left = jack_port_get_buffer(mixer_ptr->main_mix_channel.port_left, nframes);
  out_right = jack_port_get_buffer(mixer_ptr->main_mix_channel.port_right, nframes);

  for (i = 0 ; i < nframes ; i++)
  {
    out_left[i] = 0.0;
    out_right[i] = 0.0;
  }

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

    LOG_DEBUG(
      "%u: CC#%u -> %u",
      (unsigned int)(in_event.buffer[0] & 0x0F),
      (unsigned int)in_event.buffer[1],
      (unsigned int)in_event.buffer[2]);

    channel_ptr = mixer_ptr->midi_cc_map[in_event.buffer[1]].channel_ptr;
    if (channel_ptr != NULL)    /* if we have mapping for particular CC */
    {
      if (mixer_ptr->midi_cc_map[in_event.buffer[1]].balance)
      {
        channel_ptr->balance = ((float)in_event.buffer[2] / 127 - 0.5) * 2;
        LOG_DEBUG("\"%s\" volume -> %f", channel_ptr->name, channel_ptr->balance);
      }
      else
      {
        channel_ptr->volume = (float)in_event.buffer[2] / 127;

        LOG_DEBUG("\"%s\" volume -> %f", channel_ptr->name, channel_ptr->volume);
      }

      calc_channel_volumes(channel_ptr);
    }
  }

  in_right = NULL;              /* disable warning */

  /* process input channels and mix them into main mix */
  list_for_each(node_ptr, &mixer_ptr->channels_list)
  {
    channel_ptr = list_entry(node_ptr, struct channel, siblings);

    in_left = jack_port_get_buffer(channel_ptr->port_left, nframes);

    if (channel_ptr->stereo)
    {
      in_right = jack_port_get_buffer(channel_ptr->port_right, nframes);
    }

    for (i = 0 ; i < nframes ; i++)
    {
      if (!FLOAT_EXISTS(in_left[i]))
      {
        channel_ptr->NaN_detected = true;
        break;
      }

      frame_left = in_left[i] * channel_ptr->volume_left;
      out_left[i] += frame_left;

      if (channel_ptr->stereo)
      {
        frame_right = in_right[i] * channel_ptr->volume_right;

        if (!FLOAT_EXISTS(in_right[i]))
        {
          channel_ptr->NaN_detected = true;
          break;
        }
      }
      else
      {
        frame_right = in_left[i] * channel_ptr->volume_right;
      }
      out_right[i] += frame_right;

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

  /* process main mix channel */
  for (i = 0 ; i < nframes ; i++)
  {
    out_left[i] = out_left[i] * mixer_ptr->main_mix_channel.volume_left;
    out_right[i] = out_right[i] * mixer_ptr->main_mix_channel.volume_right;

    frame_left = fabsf(out_left[i]);
    if (mixer_ptr->main_mix_channel.peak_left < frame_left)
    {
      mixer_ptr->main_mix_channel.peak_left = frame_left;

      if (frame_left > mixer_ptr->main_mix_channel.abspeak)
      {
        mixer_ptr->main_mix_channel.abspeak = frame_left;
      }
    }

    frame_right = fabsf(out_right[i]);
    if (mixer_ptr->main_mix_channel.peak_right < frame_right)
    {
      mixer_ptr->main_mix_channel.peak_right = frame_right;

      if (frame_right > mixer_ptr->main_mix_channel.abspeak)
      {
        mixer_ptr->main_mix_channel.abspeak = frame_right;
      }
    }

    mixer_ptr->main_mix_channel.peak_frames++;
    if (mixer_ptr->main_mix_channel.peak_frames >= PEAK_FRAMES_CHUNK)
    {
      mixer_ptr->main_mix_channel.meter_left = mixer_ptr->main_mix_channel.peak_left;
      mixer_ptr->main_mix_channel.peak_left = 0.0;

      mixer_ptr->main_mix_channel.meter_right = mixer_ptr->main_mix_channel.peak_right;
      mixer_ptr->main_mix_channel.peak_right = 0.0;

      mixer_ptr->main_mix_channel.peak_frames = 0;
    }
  }

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

  INIT_LIST_HEAD(&mixer_ptr->channels_list);

  mixer_ptr->channels_count = 0;
  mixer_ptr->soloed_channels_count = 0;

  for (i = 0 ; i < 128 ; i++)
  {
    mixer_ptr->midi_cc_map[i].channel_ptr = NULL;
  }

  mixer_ptr->midi_cc_map[7].channel_ptr = &mixer_ptr->main_mix_channel;
  mixer_ptr->midi_cc_map[7].balance = false;
  mixer_ptr->main_mix_channel.cc_map_volume_ptr_ptr = &mixer_ptr->midi_cc_map[7].channel_ptr;

  mixer_ptr->midi_cc_map[8].channel_ptr = &mixer_ptr->main_mix_channel;
  mixer_ptr->midi_cc_map[8].balance = true;
  mixer_ptr->main_mix_channel.cc_map_balance_ptr_ptr = &mixer_ptr->midi_cc_map[8].channel_ptr;

  LOG_DEBUG("Initializing JACK");
  mixer_ptr->jack_client = jack_client_new(jack_client_name_ptr);
  if (mixer_ptr->jack_client == NULL)
  {
    LOG_ERROR("Cannot create JACK client.");
    LOG_NOTICE("Please make sure JACK daemon is running.");
    goto exit_free;
  }

  LOG_DEBUG("JACK client created");

  LOG_DEBUG("Sample rate: %" PRIu32, jack_get_sample_rate(mixer_ptr->jack_client));

  mixer_ptr->main_mix_channel.mixer_ptr = mixer_ptr;

  mixer_ptr->port_midi_in = jack_port_register(mixer_ptr->jack_client, "midi in", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
  if (mixer_ptr->port_midi_in == NULL)
  {
    LOG_ERROR("Cannot create JACK port");
    goto close_jack;
  }

  mixer_ptr->port_midi_out = jack_port_register(mixer_ptr->jack_client, "midi out", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
  if (mixer_ptr->port_midi_out == NULL)
  {
    LOG_ERROR("Cannot create JACK port");
    goto close_jack;
  }

  mixer_ptr->main_mix_channel.port_left = jack_port_register(mixer_ptr->jack_client, "main out L", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
  if (mixer_ptr->main_mix_channel.port_left == NULL)
  {
    LOG_ERROR("Cannot create JACK port");
    goto close_jack;
  }

  mixer_ptr->main_mix_channel.port_right = jack_port_register(mixer_ptr->jack_client, "main out R", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
  if (mixer_ptr->main_mix_channel.port_right == NULL)
  {
    LOG_ERROR("Cannot create JACK port");
    goto close_jack;
  }

  mixer_ptr->main_mix_channel.stereo = true;

  mixer_ptr->main_mix_channel.volume = 0.0;
  mixer_ptr->main_mix_channel.balance = 0.0;
  mixer_ptr->main_mix_channel.muted = false;
  mixer_ptr->main_mix_channel.soloed = false;
  mixer_ptr->main_mix_channel.meter_left = 0.0;
  mixer_ptr->main_mix_channel.meter_right = 0.0;
  mixer_ptr->main_mix_channel.abspeak = 0.0;

  mixer_ptr->main_mix_channel.peak_left = 0.0;
  mixer_ptr->main_mix_channel.peak_right = 0.0;
  mixer_ptr->main_mix_channel.peak_frames = 0;

  mixer_ptr->main_mix_channel.NaN_detected = false;

  calc_channel_volumes(&mixer_ptr->main_mix_channel);

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
  if (mixer_ctx_ptr->jack_client != NULL)
  {
    jack_client_close(mixer_ctx_ptr->jack_client);
  }

  free(mixer_ctx_ptr);
}

jack_mixer_channel_t
get_main_mix_channel(
  jack_mixer_t mixer)
{
  return &mixer_ctx_ptr->main_mix_channel;
}

unsigned int
get_channels_count(
  jack_mixer_t mixer)
{
  return mixer_ctx_ptr->channels_count;
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
  int i;

  channel_ptr = malloc(sizeof(struct channel));
  if (channel_ptr == NULL)
  {
    goto exit;
  }

  channel_ptr->mixer_ptr = mixer_ctx_ptr;

  channel_ptr->name = strdup(channel_name);
  if (channel_ptr->name == NULL)
  {
    goto exit_free_channel;
  }

  if (stereo)
  {
    channel_name_size = strlen(channel_name);
    port_name = malloc(channel_name_size + 3);
    memcpy(port_name, channel_name, channel_name_size);
    port_name[channel_name_size] = ' ';
    port_name[channel_name_size+1] = 'L';
    port_name[channel_name_size+2] = 0;
    channel_ptr->port_left = jack_port_register(channel_ptr->mixer_ptr->jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    port_name[channel_name_size+1] = 'R';
    channel_ptr->port_right = jack_port_register(channel_ptr->mixer_ptr->jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    free(port_name);
  }
  else
  {
    channel_ptr->port_left = jack_port_register(channel_ptr->mixer_ptr->jack_client, channel_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
  }

  channel_ptr->stereo = stereo;

  channel_ptr->volume = 0.0;
  channel_ptr->balance = 0.0;
  channel_ptr->muted = false;
  channel_ptr->soloed = false;
  channel_ptr->meter_left = -1.0;
  channel_ptr->meter_right = -1.0;
  channel_ptr->abspeak = 0.0;

  channel_ptr->peak_left = 0.0;
  channel_ptr->peak_right = 0.0;
  channel_ptr->peak_frames = 0;

  channel_ptr->NaN_detected = false;

  calc_channel_volumes(channel_ptr);

  list_add_tail(&channel_ptr->siblings, &channel_ptr->mixer_ptr->channels_list);
  channel_ptr->mixer_ptr->channels_count++;

  for (i = 11 ; i < 128 ; i++)
  {
    if (mixer_ctx_ptr->midi_cc_map[i].channel_ptr == NULL)
    {
      mixer_ctx_ptr->midi_cc_map[i].channel_ptr = channel_ptr;
      mixer_ctx_ptr->midi_cc_map[i].balance = false;
      channel_ptr->cc_map_volume_ptr_ptr = &mixer_ctx_ptr->midi_cc_map[i].channel_ptr;

      LOG_NOTICE("New channel \"%s\" volume mapped to CC#%i", channel_name, i);

      break;
    }
  }

  for (; i < 128 ; i++)
  {
    if (mixer_ctx_ptr->midi_cc_map[i].channel_ptr == NULL)
    {
      mixer_ctx_ptr->midi_cc_map[i].channel_ptr = channel_ptr;
      mixer_ctx_ptr->midi_cc_map[i].balance = true;
      channel_ptr->cc_map_balance_ptr_ptr = &mixer_ctx_ptr->midi_cc_map[i].channel_ptr;

      LOG_NOTICE("New channel \"%s\" balance mapped to CC#%i", channel_name, i);

      break;
    }
  }

  goto exit;

exit_free_channel:
  free(channel_ptr);

exit:
  return channel_ptr;
}
