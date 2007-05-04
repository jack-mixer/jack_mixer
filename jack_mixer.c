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
#include <stdio.h>
#include <stdbool.h>
#include <math.h>
#include <jack/jack.h>

#include "jack_mixer.h"
#include "list.h"

#define PEAK_FRAMES_CHUNK 4800

#define FLOAT_EXISTS(x) (!((x) - (x)))

struct channel
{
  struct list_head siblings;
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
};

struct jack_mixer
{
  jack_client_t * jack_client;
  struct list_head channels_list;
  struct channel main_mix_channel;
  int channels_count;
  int soloed_channels_count;
};

struct jack_mixer * g_the_mixer_ptr;

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

void * get_main_mix_channel()
{
  return &g_the_mixer_ptr->main_mix_channel;
}

int get_channels_count()
{
  return g_the_mixer_ptr->channels_count;
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

  if (g_the_mixer_ptr->soloed_channels_count > 0 && !channel_ptr->soloed) /* there are soloed channels but we are not one of them */
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
calc_all_channel_volumes()
{
  struct list_head * node_ptr;
  struct channel * channel_ptr;

  list_for_each(node_ptr, &g_the_mixer_ptr->channels_list)
  {
    channel_ptr = list_entry(node_ptr, struct channel, siblings);
    calc_channel_volumes(channel_ptr);
  }
}

void * add_channel(const char * channel_name, int stereo)
{
  struct channel * channel_ptr;
  char * port_name;
  size_t channel_name_size;

  channel_ptr = malloc(sizeof(struct channel));
  if (channel_ptr == NULL)
  {
    goto exit;
  }

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
    channel_ptr->port_left = jack_port_register(g_the_mixer_ptr->jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    port_name[channel_name_size+1] = 'R';
    channel_ptr->port_right = jack_port_register(g_the_mixer_ptr->jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    free(port_name);
  }
  else
  {
    channel_ptr->port_left = jack_port_register(g_the_mixer_ptr->jack_client, channel_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
  }

  channel_ptr->stereo = stereo;

  channel_ptr->volume = 0.0;
  channel_ptr->balance = 0.0;
  channel_ptr->muted = 0;
  channel_ptr->soloed = 0;
  channel_ptr->meter_left = -1.0;
  channel_ptr->meter_right = -1.0;
  channel_ptr->abspeak = 0.0;

  channel_ptr->peak_left = 0.0;
  channel_ptr->peak_right = 0.0;
  channel_ptr->peak_frames = 0;

  channel_ptr->NaN_detected = false;

  calc_channel_volumes(channel_ptr);

  list_add_tail(&channel_ptr->siblings, &g_the_mixer_ptr->channels_list);
  g_the_mixer_ptr->channels_count++;

  goto exit;

exit_free_channel:
  free(channel_ptr);

exit:
  return channel_ptr;
}

#define channel_ptr ((struct channel *)channel)

const char * channel_get_name(void * channel)
{
  return channel_ptr->name;
}

void channel_rename(void * channel, const char * name)
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

bool channel_is_stereo(void * channel)
{
  return channel_ptr->stereo;
}

void remove_channel(void * channel)
{
  list_del(&channel_ptr->siblings);
  free(channel_ptr->name);

  jack_port_unregister(g_the_mixer_ptr->jack_client, channel_ptr->port_left);
  if (channel_ptr->stereo)
  {
    jack_port_unregister(g_the_mixer_ptr->jack_client, channel_ptr->port_right);
  }

  free(channel_ptr);

  g_the_mixer_ptr->channels_count--;
}

void channel_stereo_meter_read(void * channel, double * left_ptr, double * right_ptr)
{
  *left_ptr = value_to_db(channel_ptr->meter_left);
  *right_ptr = value_to_db(channel_ptr->meter_right);
}

void channel_mono_meter_read(void * channel, double * mono_ptr)
{
  *mono_ptr = value_to_db(channel_ptr->meter_left);
}

void channel_volume_write(void * channel, double volume)
{
  channel_ptr->volume = db_to_value(volume);
  calc_channel_volumes(channel_ptr);
}

void channel_balance_write(void * channel, double balance)
{
  channel_ptr->balance = balance;
  calc_channel_volumes(channel_ptr);
}

double channel_abspeak_read(void * channel)
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

void channel_abspeak_reset(void * channel)
{
  channel_ptr->abspeak = 0;
  channel_ptr->NaN_detected = false;
}

void channel_mute(void * channel)
{
  channel_ptr->muted = 1;
  calc_channel_volumes(channel_ptr);
}

void channel_unmute(void * channel)
{
  channel_ptr->muted = 0;
  calc_channel_volumes(channel_ptr);
}

void channel_solo(void * channel)
{
  if (!channel_ptr->soloed)
  {
    channel_ptr->soloed = 1;
    g_the_mixer_ptr->soloed_channels_count++;

    if (g_the_mixer_ptr->soloed_channels_count == 1)
    {
      calc_all_channel_volumes();
    }
    else
    {
      calc_channel_volumes(channel_ptr);
    }
  }
}

void channel_unsolo(void * channel)
{
  if (channel_ptr->soloed)
  {
    channel_ptr->soloed = 0;
    g_the_mixer_ptr->soloed_channels_count--;

    if (g_the_mixer_ptr->soloed_channels_count == 0)
    {
      calc_all_channel_volumes();
    }
    else
    {
      calc_channel_volumes(channel_ptr);
    }
  }
}

bool channel_is_muted(void * channel)
{
  return channel_ptr->muted;
}

bool channel_is_soloed(void * channel)
{
  return channel_ptr->soloed;
}

#undef channel_ptr

int
process(jack_nframes_t nframes, void *arg)
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

  out_left = jack_port_get_buffer(g_the_mixer_ptr->main_mix_channel.port_left, nframes);
  out_right = jack_port_get_buffer(g_the_mixer_ptr->main_mix_channel.port_right, nframes);

  for (i = 0 ; i < nframes ; i++)
  {
    out_left[i] = 0.0;
    out_right[i] = 0.0;
  }

  in_right = NULL;              /* disable warning */

  /* process input channels and mix them into main mix */
  list_for_each(node_ptr, &g_the_mixer_ptr->channels_list)
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
    out_left[i] = out_left[i] * g_the_mixer_ptr->main_mix_channel.volume_left;
    out_right[i] = out_right[i] * g_the_mixer_ptr->main_mix_channel.volume_right;

    frame_left = fabsf(out_left[i]);
    if (g_the_mixer_ptr->main_mix_channel.peak_left < frame_left)
    {
      g_the_mixer_ptr->main_mix_channel.peak_left = frame_left;

      if (frame_left > g_the_mixer_ptr->main_mix_channel.abspeak)
      {
        g_the_mixer_ptr->main_mix_channel.abspeak = frame_left;
      }
    }

    frame_right = fabsf(out_right[i]);
    if (g_the_mixer_ptr->main_mix_channel.peak_right < frame_right)
    {
      g_the_mixer_ptr->main_mix_channel.peak_right = frame_right;

      if (frame_right > g_the_mixer_ptr->main_mix_channel.abspeak)
      {
        g_the_mixer_ptr->main_mix_channel.abspeak = frame_right;
      }
    }

    g_the_mixer_ptr->main_mix_channel.peak_frames++;
    if (g_the_mixer_ptr->main_mix_channel.peak_frames >= PEAK_FRAMES_CHUNK)
    {
      g_the_mixer_ptr->main_mix_channel.meter_left = g_the_mixer_ptr->main_mix_channel.peak_left;
      g_the_mixer_ptr->main_mix_channel.peak_left = 0.0;

      g_the_mixer_ptr->main_mix_channel.meter_right = g_the_mixer_ptr->main_mix_channel.peak_right;
      g_the_mixer_ptr->main_mix_channel.peak_right = 0.0;

      g_the_mixer_ptr->main_mix_channel.peak_frames = 0;
    }
  }

  return 0;      
}

bool init(const char * jack_client_name_ptr)
{
  int ret;

  g_the_mixer_ptr = malloc(sizeof(struct jack_mixer));
  if (g_the_mixer_ptr == NULL)
  {
    goto exit;
  }

  INIT_LIST_HEAD(&g_the_mixer_ptr->channels_list);

  printf("Initializing JACK\n");
  g_the_mixer_ptr->jack_client = jack_client_new(jack_client_name_ptr);
  if (g_the_mixer_ptr->jack_client == NULL)
  {
    fprintf(stderr, "Cannot create JACK client.\n");
    fprintf(stderr, "Please make sure JACK daemon is running.\n");
    goto exit_free;
  }

  printf("JACK client created\n");

  printf("Sample rate: %" PRIu32 "\n", jack_get_sample_rate(g_the_mixer_ptr->jack_client));

  g_the_mixer_ptr->main_mix_channel.port_left = jack_port_register(g_the_mixer_ptr->jack_client, "main out L", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
  if (g_the_mixer_ptr->main_mix_channel.port_left == NULL)
  {
    fprintf(stderr, "Cannot create JACK port");
    goto close_jack;
  }

  g_the_mixer_ptr->main_mix_channel.port_right = jack_port_register(g_the_mixer_ptr->jack_client, "main out R", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
  if (g_the_mixer_ptr->main_mix_channel.port_right == NULL)
  {
    fprintf(stderr, "Cannot create JACK port");
    goto close_jack;
  }

  g_the_mixer_ptr->main_mix_channel.stereo = true;

  g_the_mixer_ptr->main_mix_channel.volume = 0.0;
  g_the_mixer_ptr->main_mix_channel.balance = 0.0;
  g_the_mixer_ptr->main_mix_channel.muted = 0;
  g_the_mixer_ptr->main_mix_channel.soloed = 0;
  g_the_mixer_ptr->main_mix_channel.meter_left = 0.0;
  g_the_mixer_ptr->main_mix_channel.meter_right = 0.0;
  g_the_mixer_ptr->main_mix_channel.abspeak = 0.0;

  g_the_mixer_ptr->main_mix_channel.peak_left = 0.0;
  g_the_mixer_ptr->main_mix_channel.peak_right = 0.0;
  g_the_mixer_ptr->main_mix_channel.peak_frames = 0;

  g_the_mixer_ptr->main_mix_channel.NaN_detected = false;

  calc_channel_volumes(&g_the_mixer_ptr->main_mix_channel);

	ret = jack_set_process_callback(g_the_mixer_ptr->jack_client, process, NULL);
  if (ret != 0)
  {
    fprintf(stderr, "Cannot set JACK process callback");
    goto close_jack;
  }

  ret = jack_activate(g_the_mixer_ptr->jack_client);
  if (ret != 0)
  {
    fprintf(stderr, "Cannot activate JACK client");
    goto close_jack;
  }

  return true;

close_jack:
  jack_client_close(g_the_mixer_ptr->jack_client); /* this should clear all other resources we obtained through the client handle */

exit_free:
  free(g_the_mixer_ptr);

exit:
  return false;
}

void uninit()
{
  printf("Uninitializing JACK\n");
  if (g_the_mixer_ptr->jack_client != NULL)
  {
    jack_client_close(g_the_mixer_ptr->jack_client);
  }

  free(g_the_mixer_ptr);
}
