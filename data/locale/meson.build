if get_option('gui').enabled()
    languages = ['de', 'es', 'fr']
    msgfmt = find_program('msgfmt')

    foreach lang : languages
        target = meson.project_name() + '-' + lang
        po_file = target + '.po'
        mo_file = meson.project_name() + '.mo'
        msg_dir = join_paths(get_option('localedir'), lang, 'LC_MESSAGES')

        mo = configure_file(
            input: po_file,
            output: target + '.mo',
            command: [msgfmt, '-o', '@OUTPUT@', '@INPUT@'],
        )
        install_data(mo, rename: mo_file, install_dir: msg_dir)
    endforeach
endif
