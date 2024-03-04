import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import gettext
import locale
import threading

# i18n
APP = "jargonaut"
LOCALE_DIR = "/usr/share/locale"
locale.bindtextdomain(APP, LOCALE_DIR)
gettext.bindtextdomain(APP, LOCALE_DIR)
gettext.textdomain(APP)
_ = gettext.gettext

color_palette = [
    "#E6194B",  # Red
    "#3CB44B",  # Green
    "#D1A75A",  # Jaune
    "#4363D8",  # Bleu
    "#F58231",  # Orange
    "#911EB4",  # Violet
    "#42D4F4",  # Cyan
    "#F032E6",  # Magenta
    "#7BDC9A",  # Vert clair
    "#efb6b6",  # Rose
    "#469990",  # Vert d'eau
    "#d3afeb",  # Lavande
    "#9A6324",  # Brun
    "#800000",  # Marron
    "#AAFFC3",  # Vert menthe
    "#808000",  # Olive
    "#000075",  # Bleu marine
    "#A5A5A5"   # Gris
]

# Used as a decorator to run things in the background
def _async(func):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    return wrapper

# Used as a decorator to run things in the main loop, from another thread
def idle(func):
    def wrapper(*args):
        GLib.idle_add(func, *args)
    return wrapper

def build_menu(app, window, menu):
        accel_group = Gtk.AccelGroup()
        window.add_accel_group(accel_group)
        item = Gtk.ImageMenuItem()
        item.set_image(Gtk.Image.new_from_icon_name("preferences-desktop-keyboard-shortcuts-symbolic", Gtk.IconSize.MENU))
        item.set_label(_("Keyboard Shortcuts"))
        item.connect("activate", open_keyboard_shortcuts)
        key, mod = Gtk.accelerator_parse("<Control>K")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        item = Gtk.ImageMenuItem()
        item.set_image(Gtk.Image.new_from_icon_name("help-about-symbolic", Gtk.IconSize.MENU))
        item.set_label(_("About"))
        item.connect("activate", open_about, window)
        key, mod = Gtk.accelerator_parse("F1")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        item = Gtk.ImageMenuItem(label=_("Quit"))
        image = Gtk.Image.new_from_icon_name("application-exit-symbolic", Gtk.IconSize.MENU)
        item.set_image(image)
        item.connect("activate", on_menu_quit, app)
        key, mod = Gtk.accelerator_parse("<Control>Q")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>W")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        menu.show_all()

def on_menu_quit(widget, app):
        app.quit()

def open_about(widget, window):
        dlg = Gtk.AboutDialog()
        dlg.set_transient_for(window)
        dlg.set_title(_("About"))
        dlg.set_program_name("Jargonaut")
        dlg.set_comments(_("Chat Room"))
        try:
            h = open("/usr/share/common-licenses/GPL", encoding="utf-8")
            s = h.readlines()
            gpl = ""
            for line in s:
                gpl += line
            h.close()
            dlg.set_license(gpl)
        except Exception as e:
            print(e)

        dlg.set_version("__DEB_VERSION__")
        dlg.set_icon_name("jargonaut")
        dlg.set_logo_icon_name("jargonaut")
        dlg.set_website("https://www.github.com/linuxmint/jargonaut")

        def close(w, res):
            if res == Gtk.ResponseType.CANCEL or res == Gtk.ResponseType.DELETE_EVENT:
                w.destroy()

        dlg.connect("response", close)
        dlg.show()

def open_keyboard_shortcuts(widget):
        gladefile = "/usr/share/jargonaut/shortcuts.ui"
        builder = Gtk.Builder()
        builder.set_translation_domain(APP)
        builder.add_from_file(gladefile)
        window = builder.get_object("shortcuts")
        window.set_title(_("Chat Room"))
        window.show()