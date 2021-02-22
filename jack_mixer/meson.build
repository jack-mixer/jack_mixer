# https://mesonbuild.com/Python-module.html

c_args = []

if get_option('jack-midi').enabled()
    c_args += ['-DHAVE_JACK_MIDI']
endif

if get_option('verbose')
    c_args += ['-DLOG_LEVEL=0']
else
    c_args += ['-DLOG_LEVEL=2']
endif


# Build and install the extension module
module = python.extension_module(
    '_jack_mixer',
    [jack_mixer_cython, jack_mixer_sources],
    dependencies: [
        python.dependency(),
        glib_dep,
        jack_dep,
        math_dep,
    ],
    include_directories: jack_mixer_inc,
    c_args: c_args,
    install: true,
    subdir: 'jack_mixer',
)

version_py = configure_file(
    input: 'version.py.in',
    output: 'version.py',
    configuration: {
        'VERSION': meson.project_version()
    }
)


# Pure Python sources
python_sources = files([
    'abspeak.py',
    'app.py',
    'channel.py',
    'gui.py',
    '__main__.py',
    'meter.py',
    'nsmclient.py',
    'preferences.py',
    'scale.py',
    'serialization.py',
    'serialization_xml.py',
    'slider.py',
    'styling.py',
])


# Install pure Python modules
python.install_sources(
    python_sources,
    version_py,
    pure: false,
    subdir: 'jack_mixer',
)


# Install application starter script
if not get_option('wheel')
    install_data(
        '__main__.py',
        rename: 'jack_mixer',
        install_dir: bindir,
        install_mode: 'rwxr-xr-x'
    )
endif
