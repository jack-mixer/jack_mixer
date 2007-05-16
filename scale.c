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

#include <stddef.h>
#include <stdbool.h>
#include <stdlib.h>
#include <math.h>
#include <assert.h>

#include "jack_mixer.h"
//#define LOG_LEVEL LOG_LEVEL_DEBUG
#include "log.h"
#include "list.h"

struct threshold
{
  struct list_head scale_siblings;
  double db;
  double scale;
  double a;
  double b;
};

struct scale
{
  struct list_head thresholds;
};

jack_mixer_threshold_t
threshold_create(double db, double scale)
{
  struct threshold * threshold_ptr;

  threshold_ptr = malloc(sizeof(struct threshold));
  if (threshold_ptr == NULL)
  {
    return NULL;
  }

  threshold_ptr->db = db;
  threshold_ptr->scale = scale;

  LOG_DEBUG("Threshold %p created (%f dBFS -> %f)", threshold_ptr, db, scale);

  return (jack_mixer_threshold_t)threshold_ptr;
}

void
threshold_calculate_coefficients_internal(
  struct threshold * threshold_ptr,
  struct threshold * prev_ptr)
{
  threshold_ptr->a = (prev_ptr->scale - threshold_ptr->scale) / (prev_ptr->db - threshold_ptr->db);
  threshold_ptr->b = threshold_ptr->scale - threshold_ptr->a * threshold_ptr->db;
  LOG_DEBUG("%.0f dB - %.0f dB: scale = %f * dB + %f", prev_ptr->db, threshold_ptr->db, threshold_ptr->a, threshold_ptr->b);
}

#define threshold_ptr ((struct threshold *)threshold)

void
threshold_calculate_coefficients(
  jack_mixer_threshold_t threshold,
  jack_mixer_threshold_t prev)
{
  threshold_calculate_coefficients_internal(threshold_ptr, (struct threshold *)prev);
}

double
threshold_db_to_scale(
  jack_mixer_threshold_t threshold,
  double db)
{
  return threshold_ptr->a * db + threshold_ptr->b;
}

double
threshold_scale_to_db(
  jack_mixer_threshold_t threshold,
  double scale)
{
  return (scale - threshold_ptr->b) / threshold_ptr->a;
}

void
threshold_destroy(
  jack_mixer_threshold_t threshold)
{
  LOG_DEBUG("Destroying threshold %p (%f dBFS -> %f)", threshold_ptr, threshold_ptr->db, threshold_ptr->scale);
  free(threshold_ptr);
}

jack_mixer_scale_t
scale_create()
{
  struct scale * scale_ptr;

  scale_ptr = malloc(sizeof(struct scale));
  if (scale_ptr == NULL)
  {
    return NULL;
  }

  INIT_LIST_HEAD(&scale_ptr->thresholds);

  LOG_DEBUG("Scale %p created", scale_ptr);

  return (jack_mixer_scale_t)scale_ptr;
}

#define scale_ptr ((struct scale *)scale)

void
scale_destroy(
  jack_mixer_scale_t scale)
{
  free(scale_ptr);
}

void
scale_add_threshold(
  jack_mixer_scale_t scale,
  jack_mixer_threshold_t threshold)
{
  LOG_DEBUG("Adding threshold %p to scale %p", threshold_ptr, scale_ptr);
  list_add_tail(&threshold_ptr->scale_siblings, &scale_ptr->thresholds);
}

#undef threshold_ptr

void
scale_calculate_coefficients(
  jack_mixer_scale_t scale)
{
  struct threshold * threshold_ptr;
  struct threshold * prev_ptr;
  struct list_head * node_ptr;

  prev_ptr = NULL;

  list_for_each(node_ptr, &scale_ptr->thresholds)
  {
    threshold_ptr = list_entry(node_ptr, struct threshold, scale_siblings);

    LOG_DEBUG("Calculating coefficients for threshold %p", threshold_ptr);

    if (prev_ptr != NULL)
    {
      threshold_calculate_coefficients_internal(threshold_ptr, prev_ptr);
    }

    prev_ptr = threshold_ptr;
  }
}

/* Convert dBFS value to number in range 0.0-1.0 */
double
scale_db_to_scale(
  jack_mixer_scale_t scale,
  double db)
{
  struct threshold * threshold_ptr;
  struct threshold * prev_ptr;
  struct list_head * node_ptr;

  prev_ptr = NULL;

  list_for_each(node_ptr, &scale_ptr->thresholds)
  {
    threshold_ptr = list_entry(node_ptr, struct threshold, scale_siblings);

    if (db < threshold_ptr->db)
    {
      LOG_DEBUG("Match at %f dB treshold", threshold_ptr->db);
      if (prev_ptr == NULL)
      {
        return 0.0;
      }

      return threshold_db_to_scale((jack_mixer_threshold_t)threshold_ptr, db);
    }

    prev_ptr = threshold_ptr;
  }

  return 1.0;
}

/* Convert number in range 0.0-1.0 to dBFS value */
double
scale_scale_to_db(
  jack_mixer_scale_t scale,
  double scale_value)
{
  struct threshold * threshold_ptr;
  struct threshold * prev_ptr;
  struct list_head * node_ptr;

  prev_ptr = NULL;

  list_for_each(node_ptr, &scale_ptr->thresholds)
  {
    threshold_ptr = list_entry(node_ptr, struct threshold, scale_siblings);

    if (scale_value <= threshold_ptr->scale)
    {
      if (prev_ptr == NULL)
      {
        return -INFINITY;
      }

      return threshold_scale_to_db((jack_mixer_threshold_t)threshold_ptr, scale_value);
    }

    prev_ptr = threshold_ptr;
  }

  return threshold_scale_to_db((jack_mixer_threshold_t)list_entry(scale_ptr->thresholds.prev, struct threshold, scale_siblings), scale_value);
}
