# Menu .desktop file
desktop_file = 'jack_mixer.desktop'
install_data(
    desktop_file,
    install_dir: desktopdir
)

# Application icons
sizes = [
    '16x16',
    '22x22',
    '24x24',
    '32x32',
    '48x48',
]

foreach size : sizes
    install_data(
        join_paths('art', size, 'jack_mixer.png'),
        install_dir: join_paths(icondir, size, 'apps')
    )
endforeach

install_data(
    join_paths('art', 'scalable', 'jack_mixer.svg'),
    install_dir: join_paths(icondir, 'scalable', 'apps')
)

# Translations
subdir('locale')
