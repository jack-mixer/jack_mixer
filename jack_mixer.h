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

#include "scale.h"

typedef void * jack_mixer_t;
typedef void * jack_mixer_channel_t;
typedef void * jack_mixer_output_channel_t;
typedef void * jack_mixer_threshold_t;

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

jack_mixer_channel_t
add_channel(
  jack_mixer_t mixer,
  const char * channel_name,
  bool stereo);

const char *
channel_get_name(
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

/* volume is in dBFS */
void
channel_volume_write(
  jack_mixer_channel_t channel,
  double volume);

double
channel_volume_read(
  jack_mixer_channel_t channel);

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

void
channel_autoset_midi_cc(
  jack_mixer_channel_t channel);

void
remove_channel(
  jack_mixer_channel_t channel);

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

#endif /* #ifndef JACK_MIXER_H__DAEB51D8_5861_40F2_92E4_24CA495A384D__INCLUDED */
