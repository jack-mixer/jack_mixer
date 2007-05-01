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

bool init(const char * jack_client_name_ptr);

int get_channels_count();

void * add_channel(const char * channel_name, int stereo);

const char * channel_get_name(void * channel);

/* returned values are in dBFS */
void channel_stereo_meter_read(void * channel, double * left_ptr, double * right_ptr);

/* returned value is in dBFS */
void channel_mono_meter_read(void * channel, double * mono_ptr);

bool channel_is_stereo(void * channel);

/* volume is in dBFS */
void channel_volume_write(void * channel, double volume);

/* balance is from -1.0 (full left) to +1.0 (full right) */
void channel_balance_write(void * channel, double balance);

void remove_channel(void * channel);

void * get_main_mix_channel();

/* returned value is in dBFS */
double channel_abspeak_read(void * channel);

void channel_abspeak_reset(void * channel);

void channel_mute(void * channel);

void channel_unmute(void * channel);

void channel_solo(void * channel);

void channel_unsolo(void * channel);

bool channel_is_muted(void * channel);

bool channel_is_soloed(void * channel);

void channel_rename(void * channel, const char * name);

void uninit();

#endif /* #ifndef JACK_MIXER_H__DAEB51D8_5861_40F2_92E4_24CA495A384D__INCLUDED */
