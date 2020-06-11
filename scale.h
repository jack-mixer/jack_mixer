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

#ifndef JACK_SCALE_H__DAEB51D8_5861_40F2_92E4_24CA495A384D__INCLUDED
#define JACK_SCALE_H__DAEB51D8_5861_40F2_92E4_24CA495A384D__INCLUDED

typedef void * jack_mixer_scale_t;

jack_mixer_scale_t
scale_create();

bool
scale_add_threshold(
  jack_mixer_scale_t scale,
  float db,
  float scale_value);

void
scale_calculate_coefficients(
  jack_mixer_scale_t scale);

double
scale_db_to_scale(
  jack_mixer_scale_t scale,
  double db);

double
scale_scale_to_db(
  jack_mixer_scale_t scale,
  double scale_value);

void
scale_destroy(
  jack_mixer_scale_t scale);

#endif /* #ifndef JACK_SCALE_H__DAEB51D8_5861_40F2_92E4_24CA495A384D__INCLUDED */
