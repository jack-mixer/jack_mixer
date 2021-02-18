/* -*- Mode: C ; c-basic-offset: 2 -*- */
/*****************************************************************************
 *
 *   Copyright (C) 2006,2007 Nedko Arnaudov <nedko@arnaudov.name>
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

#ifndef LOG_H__7097F6FE_4FEE_4962_9542_60375961F567__INCLUDED
#define LOG_H__7097F6FE_4FEE_4962_9542_60375961F567__INCLUDED

void jack_mixer_log(int level, const char * format, ...);

#define LOG_LEVEL_DEBUG      0
#define LOG_LEVEL_INFO       1
#define LOG_LEVEL_WARNING    2
#define LOG_LEVEL_NOTICE     3
#define LOG_LEVEL_ERROR      4
#define LOG_LEVEL_FATAL      5
#define LOG_LEVEL_BLACK_HOLE 6      

#if !defined(LOG_LEVEL)
#define LOG_LEVEL LOG_LEVEL_WARNING
#endif

#if LOG_LEVEL <= LOG_LEVEL_DEBUG
# define LOG_DEBUG(format, ...)              \
  jack_mixer_log(LOG_LEVEL_DEBUG,               \
                 format "\n", ## __VA_ARGS__)
#else
# define LOG_DEBUG(format, ...)
#endif

#if LOG_LEVEL <= LOG_LEVEL_INFO
# define LOG_INFO(format, ...)               \
  jack_mixer_log(LOG_LEVEL_INFO,                \
                 format "\n", ## __VA_ARGS__)
#else
# define LOG_INFO(format, ...)
#endif

#if LOG_LEVEL <= LOG_LEVEL_WARNING
# define LOG_WARNING(format, ...)            \
  jack_mixer_log(LOG_LEVEL_WARNING,             \
                 format "\n", ## __VA_ARGS__)
#else
# define LOG_WARNING(format, ...)
#endif

#if LOG_LEVEL <= LOG_LEVEL_NOTICE
# define LOG_NOTICE(format, ...)             \
  jack_mixer_log(LOG_LEVEL_NOTICE,              \
                 format "\n", ## __VA_ARGS__)
#else
# define LOG_NOTICE(format, ...)
#endif

#if LOG_LEVEL <= LOG_LEVEL_ERROR
# define LOG_ERROR(format, ...)              \
  jack_mixer_log(LOG_LEVEL_ERROR,               \
                 format "\n", ## __VA_ARGS__)
#else
# define LOG_ERROR(format, ...)
#endif

#if LOG_LEVEL <= LOG_LEVEL_FATAL
# define LOG_FATAL(format, ...)              \
  jack_mixer_log(LOG_LEVEL_FATAL,               \
                 format "\n", ## __VA_ARGS__)
#else
# define LOG_FATAL(format, ...)
#endif

#endif /* #ifndef LOG_H__7097F6FE_4FEE_4962_9542_60375961F567__INCLUDED */
