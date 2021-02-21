jack_mixer_sources = files([
    'jack_mixer.c',
    'log.c',
    'scale.c'
])

jack_mixer_inc = include_directories('.')


# Build 'jack_mix_box' command line program
executable(
    'jack_mix_box',
    ['jack_mix_box.c', jack_mixer_sources],
    dependencies: [
        glib_dep,
        jack_dep,
        math_dep
    ],
    include_directories: jack_mixer_inc,
    c_args: get_option('jack-midi').enabled() ? '-DHAVE_JACK_MIDI' : [],
    install: true,
)


# Generate extension module C source from Cython sources
if get_option('gui').enabled()
    fs = import('fs')

    jack_mixer_mod_pyx = '_jack_mixer.pyx'
    jack_mixer_mod_c = '_jack_mixer.c'

    cython = find_program('cython', required: false)

    if fs.exists(jack_mixer_mod_c)
        jack_mixer_cython = files(jack_mixer_mod_c)
    elif cython.found()
        jack_mixer_mod_pxd = '_jack_mixer.pxd'

        jack_mixer_cython = custom_target(
            'jack_mixer_cython',
            output: jack_mixer_mod_c,
            input: jack_mixer_mod_pyx,
            depend_files: [jack_mixer_mod_pyx, jack_mixer_mod_pxd],
            command: [cython, '-o', '@OUTPUT@', '@INPUT@'],
        )
    else
        error('The \'cython\' program was not found but is required.\n' +
              'Please install Cython from: https://pypi.org/project/Cython/.')
    endif

    meson.add_dist_script('meson_dist_cython.py', jack_mixer_mod_c)
endif
