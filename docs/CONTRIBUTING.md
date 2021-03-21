# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.


## Types of Contributions

You can contribute in many ways:


### Report Bugs

Report bugs at <https://github.com/jack-mixer/jack_mixer/issues>.

If you are reporting a bug, please include:

- Your operating system name and version.
- The **jack_mixer** version (see the "About" dialog).
- The Python version (`python --version`).
- A description of what went wrong ("X doesn't work" is *not enough!*).
- Detailed steps to reproduce the bug.
- Any details about your local setup that might be helpful in troubleshooting.


### Fix Bugs or Implement Features and Enhancements

Look through the GitHub issues for for anything tagged with "bug", "feature
request" or "enhancement" and if you think you can help out, leave a comment
on the issue saying what you intend to work on and in which timeframe.


### Write Documentation

**jack_mixer** could definitely use more documentation, whether it is more
detailed man pages or a real user guide, better docstrings or comments in the
code, or even third-party tutorials, video or quick tips on social media.

If you want to help out with the documentation, please get in touch with the
**jack_mixer** maintainers via the Github issue tracker, email or on IRC
(see [README] for contact information)


### Add or Update Translations

We would like to translate the user interface of **jack_mixer** in as many
languages as possible and keep existing translations as up-to-date and
error-free as possible.

See the [Translations](#translations) section below.


### Submit Feedback

The best way to send feedback is to also file an issue at
<https://github.com/jack-mixer/jack_mixer/issues>.

If you are proposing a feature:

- Give a short and poignant title to your feature request issue.
- Explain in detail how it would work.
- Keep the scope as narrow as possible, to make it easier to implement.
- Remember that this is a volunteer-driven project, and that contributions are
  welcome :)


## Development


### Development Environment Setup and Workflow

Ready to work on **jack_mixer**? First you should set up your local
development environment:

1. Fork the [jack-mixer/jack_mixer] repo on GitHub.

2. Clone your fork locally:

        $ git clone git@github.com:your_name_here/jack_mixer.git

3. Install all build and run-time requirements listed in the [INSTALL] file and
   make sure you can configure and build the application with `meson` as
   described in the same document.

4. Install `flake8`, `isort` and `black` either via your distribution's
   package management or with `pip install`.

5. Create a branch for local development of your new feature or bugfix:

        $ git checkout -b bugfix/what-does-this-fix

   or:

        $ git checkout -b feature/what-does-this-do

   Now you're ready to make your changes, make sure you follow the
   [Coding Guidelines](#coding-guidelines) outlined below.

6. Commit your changes and push your branch to GitHub:

        $ git add .
        $ git commit -m "Detailed description of your changes."
        $ git push -u origin name-of-your-bugfix-or-feature

7. Submit a pull request through the GitHub website.

Create a new branch for every new PR, starting from the `main` branch.


### Coding Guidelines


#### Python Code

- Check all Python code with `flake8` and fix all warnings and errors or
  explicitly silence them (and be ready to explain why you did this when
  your changes are reviewed).
- Format all Python code with `isort` and `black`.
- Line-endings should should be Unix style (`\n`), not Windows style (`\r\n`).
- Cython files should follow the same formatting rules as Python source code,
  where possible.
- The Python code must work for all supported Python 3 versions
  (see `pyproject.toml`).


#### C Code

- Opening brackets go on their own line:
```
    if (condition)
    {
        stuff;
    }
```
- There should be a space between keywords and parenthesis for:
  `if`, `else`, `while`, `switch`, `catch`, `function`.
- Function calls have no space before the parentheses.
- No spaces are left inside the parentheses.
- A space after each comma, but without space before.
- All binary operators must have one space before and one after.
- There should be no empty comments.

These conventions may change in the future and we may introduce auto-formatting
of C code with `clang-format` at some point.


## Translations


### Adding a New Translation

1. Copy `data/local/jack_mixer.pot` to `data/locale/jack_mixer-<lang>.po`,
   where `<lang>` is the two-letter code for the language of the new
   translation.
2. Edit `data/local/meson.build` and add a string with the language code for
   the new translation to the `languages` array (keep it sorted
   alphabetically).
3. Edit `jack-mixer-<lang>.po` and translate all messages (you only need to
   translate the messages for `argparse`, which are used in the command line
   help text).
4. Run `./tools/compile-messages.py` to compile all `*.po` files to `*.mo`
   files.
5. Build the application with `meson` and then run it from the root of the
   source directory using the `./tools/jack_mixer.sh` script and check your
   translations. Also use the `-h` command line option to check the translation
   of the usage help message.
6. Add a `Comment` tag in the new language to the `data/jack_mixer.desktop`
   file.
7. Commit the `jack-mixer-<lang>.po` file and your changes to the `.desktop`
   and `data/locale/meson.build` files to a new branch and make a Pull Request.


### Updating a Translation

When the timestamp listed in `data/local/jack_mixer.pot` is newer than a
translation `.po` file, it may contain updated or new messages, which need to
be translated.

Run the `./tools/merge-messages.py` script to update all `*.po` files
and then edit the `.po` for the language translation you want to update. Use
`git diff jack-mixer-<lang>.po` to check for new or updated messages.

When you have made your edits, check the new translations as described above
and make a new Pull Request (only include the `.po` files, which you edited).


[jack-mixer/jack_mixer]: https://github.com/jack-mixer/jack_mixer
[INSTALL]: ../INSTALL.md
[README]: ../README.md