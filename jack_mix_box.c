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
#include <getopt.h>
#include "jack_mixer.h"

void
usage()
{

	printf("Usage:\n");
	printf("\tjack_mix_box [ -n|--name JACK_CLI_NAME ] [ -s|--stereo ] MIDI_CC_1 MIDI_CC_2 ....\n\n");
}

int
main(int argc, char *argv[])
{
	jack_mixer_scale_t scale;
	jack_mixer_t mixer;
	jack_mixer_channel_t main_mix_channel;
	char *jack_cli_name = NULL;
	int channel_index;
	bool bStereo = false;

	while (1) {
		int c;
		static struct option long_options[] =
		{
			{"name",  required_argument, 0, 'n'},
			{"help",  required_argument, 0, 'h'},
			{"stereo",  required_argument, 0, 's'},
			{0, 0, 0, 0}
		};
		int option_index = 0;

		c = getopt_long (argc, argv, "shn:", long_options, &option_index);
		if (c == -1)
			break;

		switch (c) {
			case 'n':
				jack_cli_name = strdup(optarg);
				break;
			case 's':
				bStereo = true;
				break;
			case 'h':
				usage();
				exit(0);
				break;
			default:
				fprintf(stderr, "Unknown argument, aborting.\n");
				exit(1);
		}
	}

	if (optind == argc) {
		fprintf(stderr, "You must specify at least one input channel\n");
		exit(1);
	}

	scale = scale_create();
	scale_add_threshold(scale, -70.0, 0.0);
	scale_add_threshold(scale, 0.0, 1.0);
	scale_calculate_coefficients(scale);

	if (jack_cli_name == NULL) {
		jack_cli_name = strdup("jack_mix_box");
	}

	mixer = create(jack_cli_name, false);
	main_mix_channel = add_output_channel(mixer, "MAIN", true, false);
	channel_set_midi_scale(main_mix_channel, scale);
	channel_volume_write(main_mix_channel, 0.0);

	channel_index = 0;
	while (optind < argc) {
		char *channel_name;
		jack_mixer_channel_t channel;

		channel_index += 1;
		channel_name = malloc(15);
		if (snprintf(channel_name, 15, "Channel %d", channel_index) >= 15) {
			abort();
		}
		channel = add_channel(mixer, channel_name, bStereo);
		if (channel == NULL) {
			fprintf(stderr, "Failed to add channel %d, aborting\n", channel_index);
			exit(1);
		}
		channel_set_volume_midi_cc(channel, atoi(argv[optind++]));
		channel_set_midi_scale(channel, scale);
		channel_volume_write(channel, -70);
	}

	while (true) {
		sleep(1);
	}

	return 0;
}
