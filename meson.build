project(
    'jack_mixer',
    'c',
    version: '18',
    license: 'GPL2+',
    default_options: [
        'warning_level=2'
    ],
    meson_version: '>=0.64.0'
)

# Dependencies
cc = meson.get_compiler('c')
glib_dep = dependency('glib-2.0')
math_dep = cc.find_library('m', required: false)
jack2_dep = dependency('jack', version:'>=1.9.11', required: false)
jack1_dep = dependency('jack', version:'>=0.125.0, <1.0', required: false)

if not jack2_dep.found() and jack1_dep.found()
    jack_dep = jack1_dep
elif jack2_dep.found()
    jack_dep = jack2_dep
else
    error('No recent enough (jack2>=1.9.11 or jack1>=0.125.0) version of JACK found.')
endif

if get_option('gui').disabled() and get_option('jack-midi').disabled()
    error('Disabling both GUI and JACK-MIDI is not supported.')
endif

if get_option('gui').enabled()
    pymod = import('python')
    python = pymod.find_installation(
        'python3',
        required: true,
        pure: false,
        modules: get_option('check-py-modules') ? ['gi', 'cairo', 'appdirs'] : []
    )
endif

# Installation directories
prefix = get_option('prefix')
bindir = join_paths(prefix, get_option('bindir'))
datadir = join_paths(prefix, get_option('datadir'))
#localedir = join_paths(prefix, get_option('localedir'))
#pythondir = join_paths(prefix, python.get_path('purelib'))
desktopdir = join_paths(datadir, 'applications')
icondir = join_paths(datadir, 'icons', 'hicolor')
raysessiondir = join_paths('/', 'etc', 'xdg', 'raysession', 'client_templates', '35_jackmixer')

# Build jack_mix_box and generate _jack_mixer extension source
subdir('src')

# Build & install C extension module and Python package
if get_option('gui').enabled()
    subdir('jack_mixer')
endif

# Install desktop file and icons
if get_option('gui').enabled()
    subdir('data')
endif

# Install documentation
subdir('docs')

if get_option('gui').enabled() and not get_option('wheel')
    meson.add_install_script('meson_postinstall.py')
endif

summary({
    'Build jack_mixer GUI': get_option('gui').enabled(),
    'JACK MIDI support': get_option('jack-midi').enabled(),
    'Debug messages (verbose)': get_option('verbose'),
    'Build for wheel': get_option('wheel'),
}, section: 'Configuration')
