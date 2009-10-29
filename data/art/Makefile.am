# ******************************************************************************
# Images and icon
# ******************************************************************************

16icondir = $(datadir)/icons/hicolor/16x16/apps
16icon_DATA = 16x16/jack_mixer.png

22icondir = $(datadir)/icons/hicolor/22x22/apps
22icon_DATA = 22x22/jack_mixer.png

24icondir = $(datadir)/icons/hicolor/24x24/apps
24icon_DATA = 24x24/jack_mixer.png

32icondir = $(datadir)/icons/hicolor/32x32/apps
32icon_DATA = 32x32/jack_mixer.png

48icondir = $(datadir)/icons/hicolor/48x48/apps
48icon_DATA = 48x48/jack_mixer.png

svgicondir = $(datadir)/icons/hicolor/scalable/apps
svgicon_DATA = scalable/jack_mixer.svg

gtk_update_icon_cache = gtk-update-icon-cache -f -t $(datadir)/icons/hicolor

install-data-hook: update-icon-cache
uninstall-hook: update-icon-cache
update-icon-cache:
	@-if test -z "$(DESTDIR)"; then \
		echo "Updating Gtk icon cache."; \
		$(gtk_update_icon_cache); \
	else \
		echo "*** Icon cache not updated.  After (un)install, run this:"; \
		echo "***   $(gtk_update_icon_cache)"; \
	fi

EXTRA_DIST = \
	$(16icon_DATA) \
	$(22icon_DATA) \
	$(24icon_DATA) \
	$(32icon_DATA) \
	$(48icon_DATA) \
	$(svgicon_DATA) \
	16x16/jack_mixer.svg \
	22x22/jack_mixer.svg \
	32x32/jack_mixer.svg \
	48x48/jack_mixer.svg

