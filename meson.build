project('jack_mixer', 'c',
        version : '13rc1',
        license : 'GPL2+',
        default_options : ['warning_level=3'])

cc = meson.get_compiler('c')
glib_dep = dependency('glib-2.0')
jack_dep = dependency('jack')
math_dep = cc.find_library('m', required : false)

jack_mix_box_sources = files([
    'jack_mix_box.c',
    'jack_mixer.c',
    'log.c',
    'scale.c'
])

executable('jack_mix_box',
           jack_mix_box_sources,
           dependencies : [glib_dep, jack_dep, math_dep],
           c_args : get_option('jack-midi').enabled() ? '-DHAVE_JACK_MIDI' : [],
           install : true)
