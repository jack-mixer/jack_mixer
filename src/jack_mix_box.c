/*****************************************************************************
 *
 *   This file is part of jack_mixer
 *
 *   Copyright (C) 2006 Nedko Arnaudov <nedko@arnaudov.name>
 *   Copyright (C) 2009-2011 Frederic Peters <fpeters@0d.be>
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

/*
 * jack_mix_box is a most minimalistic jack mixer, a set of mono/sterero input
 * channels, mixed to a single output channel, with the volume of the
 * input channels controlled by MIDI control change (CC) codes.
 *
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <libintl.h>
#include <locale.h>
#include <getopt.h>
#include <signal.h>
#include <unistd.h>
#include "jack_mixer.h"

#define _(String) gettext(String)

jack_mixer_t mixer;
bool keepRunning = true;

void
usage()
{
	const char* _usage = _(
"Usage: "
"jack_mix_box [-n <name>] [-p] [-s] [-v <dB>|-v <dB>|...] MIDI_CC...\n"
"\n"
"-h|--help    print this help message\n"
"-n|--name    set JACK client name\n"
"-p|--pickup  enable MIDI pickup mode (default: jump-to-value)\n"
"-s|--stereo  make all input channels stereo with left+right input\n"
"-v|--volume  initial volume gain in dBFS (default 0.0, i.e. unity gain)\n"
"             (may be used 0,1 or as many times as there are MIDI_CC arguments)\n"
"\n"
"Each positional argument is interpreted as a MIDI Control Change number and\n"
"adds a mixer channel with one (mono) or left+right (stereo) inputs, whose\n"
"volume can be controlled via the given MIDI Control Change.\n"
"\n"
"Send SIGUSR1 to the process to have the current volumes reported per input\n"
"channel.\n\n");
	fputs(_usage, stdout);
}

void
reportVolume(int sig)
{
	(void)sig;
	channels_volumes_read(mixer);
}

void
triggerShutDown(int sig)
{
	(void)sig;
	keepRunning = false;
}

int
main(int argc, char *argv[])
{
	jack_mixer_scale_t scale;
	jack_mixer_channel_t main_mix_channel;
	char *jack_cli_name = NULL;
	int channel_index;
	bool bStereo = false;
	enum midi_behavior_mode ePickup = Jump_To_Value;
	double initialVolume[argc]; //slighty bigger array than needed, but we avoid dynamic memry allocation
	char * localedir;
	int volume_index = 0;

	initialVolume[0] = 0.0f; //in dbFS, always init the 1st input
	localedir = getenv("LOCALEDIR");
	setlocale(LC_ALL, "");
	bindtextdomain("jack_mixer", localedir != NULL ? localedir : LOCALEDIR);
	textdomain("jack_mixer");

	while (1) {
		int c;
		static struct option long_options[] =
		{
			{"name",  required_argument, 0, 'n'},
			{"help",  no_argument, 0, 'h'},
			{"pickup",  no_argument, 0, 'p'},
			{"stereo",  no_argument, 0, 's'},
			{"volume",  required_argument, 0, 'v'},
			{0, 0, 0, 0}
		};
		int option_index = 0;

		c = getopt_long (argc, argv, "sphn:v:", long_options, &option_index);
		if (c == -1)
			break;

		switch (c) {
			case 'n':
				jack_cli_name = strdup(optarg);
				break;
			case 's':
				bStereo = true;
				break;
			case 'v':
				initialVolume[volume_index++] = strtod(optarg, NULL);
				break;
			case 'h':
				usage();
				exit(0);
				break;
			case 'p':
				ePickup = Pick_Up;
				break;
			default:
				fprintf(stderr, _("ERROR: Unknown argument, aborting.\n"));
				exit(1);
		}
	}

	if (optind == argc) {
		fputs(_("ERROR: You must specify at least one input channel.\n"), stderr);
		exit(1);
	}

	if ((volume_index >= 2) && ( volume_index != (argc - optind)))
	{
		fprintf(stderr, "ERROR: need to specify either no -v option, or exactly 1 or as many -v as the number of MIDI_CC arguments (provided %d, but required %d).\n",volume_index, argc - optind);
		exit(-1);
	}

	scale = scale_create();
	scale_add_threshold(scale, -70.0, 0.0);
	scale_add_threshold(scale, 0.0, 1.0);
	scale_calculate_coefficients(scale);

	if (jack_cli_name == NULL) {
		jack_cli_name = strdup("jack_mix_box");
	}

	mixer = create(jack_cli_name, false);
	if (mixer == NULL) {
		fputs(jack_mixer_error_str(), stderr);
		return -1;
	}
	main_mix_channel = add_output_channel(mixer, "MAIN", true, false);
	channel_set_midi_scale(main_mix_channel, scale);
	channel_volume_write(main_mix_channel, 0.0);
	set_midi_behavior_mode(mixer, ePickup);

	/* extrapolate the given value for initialVolume to all the rest */
	if (volume_index < 2)
	{
		for (int i = 1; i < argc; i++)
		{
			initialVolume[i] = initialVolume[0];
		}
	}

	channel_index = 0;
	while (optind < argc) {
		char *channel_name;
		jack_mixer_channel_t channel;

		channel_index += 1;
		channel_name = malloc(15);
		if (snprintf(channel_name, 15, "Channel %d", channel_index) >= 15) {
			free(channel_name);
			abort();
		}
		channel = add_channel(mixer, channel_name, bStereo);
		if (channel == NULL) {
			fprintf(stderr, _("Failed to add channel %d, aborting.\n"), channel_index);
			exit(1);
		}
		channel_set_volume_midi_cc(channel, atoi(argv[optind++]));
		channel_set_midi_scale(channel, scale);
		channel_volume_write(channel, initialVolume[channel_index -1]);
		free(channel_name);
	}

	signal(SIGUSR1, reportVolume);
	signal(SIGTERM, triggerShutDown);
	signal(SIGHUP, triggerShutDown);
	signal(SIGINT, triggerShutDown);

	while (keepRunning) {
		usleep(500u * 1000u); //500msec
	}

	remove_channels(mixer);
	remove_output_channel(main_mix_channel);
	destroy(mixer);
	scale_destroy(scale);
	free(jack_cli_name);
	return 0;
}
