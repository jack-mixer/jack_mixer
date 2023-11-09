if not get_option('wheel')
    fs = import('fs')

    jack_mix_box_man = 'jack_mix_box.1'
    jack_mixer_man = 'jack_mixer.1'

    rst2man = find_program('rst2man', 'rst2man.py', required: false)

    if fs.exists(jack_mix_box_man)
        install_man(jack_mix_box_man)
    elif rst2man.found()
        jack_mix_box_man_rst_in = 'jack_mix_box.1.rst.in'

        jack_mix_box_man_rst = configure_file(
            input: jack_mix_box_man_rst_in,
            output: 'jack_mix_box.1.rst',
            configuration: {
                'VERSION': meson.project_version()
            }
        )

        jack_mix_box_troff = custom_target(
            'jack_mix_box_rst2man',
            output: jack_mix_box_man,
            input: jack_mix_box_man_rst,
            command: [rst2man, '@INPUT@', '@OUTPUT@'],
            install: true,
            install_dir: join_paths(get_option('mandir'), 'man1')
        )
    else
        error('Pre-generated file \'@0@\' and \'rst2man\' not found.\n'.format(jack_mix_box_man) +
              'Please install \'docutils\' from https://pypi.org/project/docutils.')
    endif

    if get_option('gui').enabled()
        if fs.exists(jack_mixer_man)
            install_man(jack_mixer_man)
        elif rst2man.found()
            jack_mixer_man_rst_in = 'jack_mixer.1.rst.in'

            jack_mixer_man_rst = configure_file(
                input: jack_mixer_man_rst_in,
                output: 'jack_mixer.1.rst',
                configuration: {
                    'VERSION': meson.project_version()
                }
            )

            jack_mixer_troff = custom_target(
                'jack_mixer_rst2man',
                output: jack_mixer_man,
                input: jack_mixer_man_rst,
                command: [rst2man, '@INPUT@', '@OUTPUT@'],
                install: true,
                install_dir: join_paths(get_option('mandir'), 'man1')
            )
        else
            error('Pre-generated file \'@0@\' and \'rst2man\' not found.\n'.format(jack_mix_box_man) +
                  'Please install \'docutils\' from https://pypi.org/project/docutils.')
        endif
    endif

    meson.add_dist_script('meson_dist_rst2man.py', jack_mixer_man, jack_mix_box_man)
endif
