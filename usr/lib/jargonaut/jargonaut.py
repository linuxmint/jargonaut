#!/usr/bin/python3

import gi
import irc.client
gi.require_version('Gtk', '3.0')
gi.require_version('XApp', '1.0')
from gi.repository import Gtk, Gio, GLib, Gdk, XApp
from irc.connection import Factory
import random
import threading
import getpass
import random
import re
import ssl
import gettext
import locale
import setproctitle

setproctitle.setproctitle("jargonaut")

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

class IRCClient(irc.client.SimpleIRCClient):
    def __init__(self, app):
        irc.client.SimpleIRCClient.__init__(self)
        self.app = app
        self.channel_users = {}

    def on_welcome(self, connection, event):
        connection.join(self.app.channel)
        connection.names([self.app.channel])

    @idle
    def on_join(self, connection, event):
        self.print_info(f"Joined channel: target={event.target} source={event.source}")
        self.app.builder.get_object("main_stack").set_visible_child_name("page_chat")
        nick = event.source.nick
        channel = event.target
        if nick not in self.channel_users[channel]:
            self.app.assign_color(nick)
            self.channel_users[channel].append(nick)
            self.app.update_users()
        if nick == self.app.nickname:
            self.identify()

    @_async
    def identify(self):
        username = self.app.settings.get_string("nickname")
        password = self.app.settings.get_string("password")
        if password != "":
            print("Identifying...")
            self.connection.privmsg("Nickserv", f"IDENTIFY {username} {password}")

    def on_namreply(self, connection, event):
        channel = event.arguments[1]
        users = event.arguments[2].split()
        clean_users = []
        for user in users:
            for character in ["~", "&", "@", "%", "+"]:
                if user.startswith(character):
                    user = user[1:]
                    break
            clean_users.append(user)
            self.app.assign_color(user)
        self.channel_users[channel] = clean_users
        self.app.update_users()

    def on_notice(self, connection, event):
        self.print_info("Notice: " + event.source + " " + event.arguments[0])

    @idle
    def on_nick(self, connection, event):
        self.print_info(f"Nick: target={event.target} source={event.source}")
        old_nick = event.source.nick
        new_nick = event.target
        if old_nick in self.channel_users[self.app.channel]:
            self.channel_users[self.app.channel].remove(old_nick)
        if not new_nick in self.channel_users[self.app.channel]:
            self.channel_users[self.app.channel].append(new_nick)
        if not new_nick in self.app.user_colors.keys():
            self.app.assign_color(new_nick)
        if old_nick == self.app.nickname:
            self.app.nickname = new_nick
            self.app.builder.get_object("label_username").set_markup(self.app.get_nick_markup(new_nick))
        self.app.update_users()

    @idle
    def on_quit(self, connection, event):
        self.print_info(f"Quit: target={event.target} source={event.source}")
        nick = event.source.nick
        channel = event.target
        if nick in self.channel_users[self.app.channel]:
            self.channel_users[self.app.channel].remove(nick)
            self.app.update_users()

    @idle
    def on_part(self, connection, event):
        self.print_info(f"Part: target={event.target} source={event.source}")
        nick = event.source.nick
        channel = event.target
        if nick in self.channel_users[channel]:
            self.channel_users[channel].remove(nick)
            self.app.update_users()

    def on_all_raw_messages(self, connection, event):
        if self.app.settings.get_boolean("debug"):
            self.print_info("Raw message: " + str(event.arguments))

    def on_pubmsg(self, connection, event):
        nick = event.source.split('!')[0]
        message = event.arguments[0]
        self.app.print_message(nick, message)

    def on_erroneusnickname(self, connection, event):
        print("Invalid nickname", event.arguments[0])
        self.app.show_error_status("dialog-error-symbolic", _("Invalid nickname"), _("Your nickname was rejected. Restart the application to reset it."))
        self.app.settings.set_string("nickname", "")

    def on_disconnect(self, connection, event):
        print("Disconnected from server: ", event.target)
        self.app.show_error_status("dialog-error-symbolic", _("Disconnected"), _("You have been disconnected from the server. Please try to reconnect."))

    def on_error(self, connection, event):
        print("Error from server: ", event.arguments[0])
        self.app.show_error_status("dialog-error-symbolic", _("Error"), _("An error occurred: ") + event.arguments[0])

    def on_nicknameinuse(self, connection, event):
        self.app.nickname =  self.app.get_new_nickname(with_random_suffix=True)
        self.app.assign_color(self.app.nickname)
        connection.nick(self.app.nickname)
        self.print_info(f"Nickname in use, switching to '{self.app.nickname}'")
        self.app.builder.get_object("label_username").set_markup(self.app.get_nick_markup(self.app.nickname))

    @idle
    def print_error(self, message):
        print("Error: " + message)

    @idle
    def print_info(self, message):
        print("Info: " + message)

class IRCApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.x.jargonaut")
        self.window = None

    def do_activate(self):
        # If the window already exists, present it to the user
        if self.window is not None:
            self.window.present()
            return

        self.is_connected = False
        self.user_colors = {}
        self.color_index = 0

        self.settings = Gio.Settings(schema="org.x.jargonaut")
        self.channel = self.settings.get_string("channel")
        self.server = self.settings.get_string("server")
        self.port = self.settings.get_int("port")
        self.tls = self.settings.get_boolean("tls-connection")
        self.nickname = self.get_new_nickname()

        self.dark_mode_manager = XApp.DarkModeManager.new(self.settings.get_boolean("prefer-dark-mode"))

        self.last_key_press_is_tab = False
        self.last_message_nick = ""

        self.builder = Gtk.Builder()
        self.builder.add_from_file("/usr/share/jargonaut/jargonaut.ui")
        self.window = self.builder.get_object("main_window")
        self.window.set_application(self)
        self.window.show_all()

        css_provider = Gtk.CssProvider()
        css_provider.load_from_path("/usr/share/jargonaut/style.css")
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Menubar
        accel_group = Gtk.AccelGroup()
        self.window.add_accel_group(accel_group)
        menu = self.builder.get_object("main_menu")
        item = Gtk.ImageMenuItem()
        item.set_image(Gtk.Image.new_from_icon_name("preferences-desktop-keyboard-shortcuts-symbolic", Gtk.IconSize.MENU))
        item.set_label(_("Keyboard Shortcuts"))
        item.connect("activate", self.open_keyboard_shortcuts)
        key, mod = Gtk.accelerator_parse("<Control>K")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        item = Gtk.ImageMenuItem()
        item.set_image(Gtk.Image.new_from_icon_name("help-about-symbolic", Gtk.IconSize.MENU))
        item.set_label(_("About"))
        item.connect("activate", self.open_about)
        key, mod = Gtk.accelerator_parse("F1")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        item = Gtk.ImageMenuItem(label=_("Quit"))
        image = Gtk.Image.new_from_icon_name("application-exit-symbolic", Gtk.IconSize.MENU)
        item.set_image(image)
        item.connect("activate", self.on_menu_quit)
        key, mod = Gtk.accelerator_parse("<Control>Q")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>W")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        menu.show_all()

        # Settings widgets
        self.bind_entry_widget("nickname", self.builder.get_object("pref_nickname"))
        self.bind_entry_widget("password", self.builder.get_object("pref_password"))
        self.bind_switch_widget("prefer-dark-mode", self.builder.get_object("pref_dark"), fn_callback=self.update_dark_mode)

        self.treeview = self.builder.get_object("treeview_chat")
        self.store = Gtk.ListStore(str, str, str) # nick, message
        self.treeview.set_model(self.store)

        renderer = Gtk.CellRendererText()
        renderer.props.xalign = 1.0
        col = Gtk.TreeViewColumn("", renderer, markup=0)
        col.set_name("first_column")
        self.treeview.append_column(col)

        # Add a dedicated column which always renders |
        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("", renderer, text=2)
        self.treeview.append_column(col)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("", renderer, markup=1)
        self.treeview.append_column(col)

        self.user_treeview = self.builder.get_object("treeview_users")
        self.user_store = Gtk.ListStore(str, str) # nick, raw_nick
        self.user_treeview.set_model(self.user_store)

        completion = Gtk.EntryCompletion()
        completion.set_model(self.user_store)
        completion.set_text_column(1)
        completion.set_inline_completion(True)
        completion.set_popup_completion(True)

        self.entry = self.builder.get_object("entry_main")
        self.entry.set_completion(completion)
        self.entry.connect("key-press-event", self.on_key_press_event)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("Users", renderer, markup=0)
        self.user_treeview.append_column(col)

        self.assign_color(self.nickname)
        self.builder.get_object("label_username").set_markup(self.get_nick_markup(self.nickname))

        self.builder.get_object("channel_stack").connect("notify::visible-child-name", self.on_page_changed)

        self.client = IRCClient(self)
        self.connect_to_server()

    @idle
    def show_error_status(self, icon_name, message, details):
        self.builder.get_object("main_stack").set_visible_child_name("page_status")
        self.builder.get_object("status_icon").set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        self.builder.get_object("status_label").set_text(message)
        self.builder.get_object("status_details").set_text(details)

    def open_about(self, widget):
        dlg = Gtk.AboutDialog()
        dlg.set_transient_for(self.window)
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

    def open_keyboard_shortcuts(self, widget):
        gladefile = "/usr/share/jargonaut/shortcuts.ui"
        builder = Gtk.Builder()
        builder.set_translation_domain(APP)
        builder.add_from_file(gladefile)
        window = builder.get_object("shortcuts")
        window.set_title(_("Chat Room"))
        window.show()

    def on_menu_quit(self, widget):
        self.quit()

    def on_page_changed(self, stack, param):
        if stack.get_visible_child_name() in ["page_questions", "page_discussion"]:
            self.builder.get_object("entry_box").show_all()
            GLib.idle_add(self.entry.grab_focus)
        else:
            self.builder.get_object("entry_box").set_visible(False)

    def update_dark_mode(self, active):
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", active)

    def bind_entry_widget(self, key, widget, fn_callback=None):
        widget.set_text(self.settings.get_string(key))
        widget.connect("changed", self.on_bound_entry_changed, key, fn_callback)

    def bind_switch_widget(self, key, widget, fn_callback=None):
        widget.set_active(self.settings.get_boolean(key))
        widget.connect("notify::active", self.on_bound_switch_activated, key, fn_callback)

    def on_bound_entry_changed(self, widget, key, fn_callback=None):
        self.settings.set_string(key, widget.get_text())
        if fn_callback is not None:
            fn_callback(widget.get_active())

    def on_bound_switch_activated(self, widget, active, key, fn_callback=None):
        self.settings.set_boolean(key, widget.get_active())
        if fn_callback is not None:
            fn_callback(widget.get_active())

    def assign_color(self, nick):
        if nick not in self.user_colors.keys():
            color = color_palette[self.color_index]
            print(f"Assigning color {color} to {nick}")
            self.user_colors[nick] = color
            self.color_index = (self.color_index + 1) % len(color_palette)

    def get_nick_markup(self, nick):
        if nick == "":
            color = "grey"
        elif nick == "*":
            color = "red"
        else:
            color = self.user_colors[nick]
        nick = f"<span foreground='{color}'>{nick}</span>"
        return nick

    def get_new_nickname(self, with_random_suffix=False):
        if self.settings.get_string("nickname") != "":
            prefix = self.settings.get_string("nickname")
        else:
            prefix = getpass.getuser()
        if with_random_suffix:
            prefix = prefix[:13] # 13 chars max + 3 chars for suffix
            suffix = '{:02x}'.format(random.randint(0, 255))
            return f"{prefix}_{suffix}"
        else:
            return prefix[:16] # 16 chars max

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        ctrl = (event.state & Gdk.ModifierType.CONTROL_MASK)
        position = widget.get_position()
        text = widget.get_text()
        if keyname == "Tab":
            if " " in text:
                return True
            if text == "":
                return True
            completion = widget.get_completion()
            model = completion.get_model()
            if len(model) > 0:
                num_matches = 0
                for row in model:
                    if row[1].startswith(text):
                        num_matches += 1
                if num_matches > 0:
                    # Adding prefix
                    completion.insert_prefix()
                    if num_matches == 1:
                        # Adding suffix (cause single match)
                        widget.set_text(text + ": ")
                    elif self.last_key_press_is_tab:
                        # Adding suffix (cause double tab)
                        widget.set_text(text + ": ")
                widget.set_position(-1)
                self.last_key_press_is_tab = True
            return True  # Stop propagation of the event
        else:
            self.last_key_press_is_tab = False
        if keyname == "Return":
            message = text.strip()
            if message != "":
                completion = widget.get_completion()
                widget.set_completion(None)
                widget.set_text("")
                widget.set_completion(completion)
                self.print_message(self.nickname, message)
                self.send_message(message)
            return True
        elif ctrl and keyname == "b":
            widget.set_text(text + "\x02")
            widget.set_position(position + 1)
            return True
        elif ctrl and keyname == "i":
            # This should be \x1D but Gtk.Entry won't accept it
            # so we use \x16 instead and we replace it when sending
            # the message
            widget.set_text(text + "\x16")
            widget.set_position(position + 1)
            return True
        elif ctrl and keyname == "u":
            widget.set_text(text + "\x1F")
            widget.set_position(position + 1)
            return True
        elif ctrl and keyname == "s":
            widget.set_text(text + "\x1E")
            widget.set_position(position + 1)
            return True

        return False

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.connect("shutdown", self.on_shutdown)

    def on_shutdown(self, application):
        if self.is_connected:
            self.disconnect()

    @_async
    def disconnect(self):
        try:
            self.client.connection.disconnect(message="Application closed")
        except Exception as e:
            print(e)

    @_async
    def send_message(self, message):
        message = message.replace('\x16', '\x1D')
        self.client.connection.privmsg(self.channel, message)

    @idle
    def print_message(self, nick, message):
        # Format text (IRC codes -> pango)
        message = re.sub(r'\x02(.*?)\x02', r'<b>\1</b>', message)
        message = re.sub(r'\x16(.*?)\x16', r'<i>\1</i>', message)
        message = re.sub(r'\x1D(.*?)\x1D', r'<i>\1</i>', message)
        message = re.sub(r'\x1F(.*?)\x1F', r'<u>\1</u>', message)
        message = re.sub(r'\x1E(.*?)\x1E', r'<s>\1</s>', message)
        sep = "|"
        nickname = nick
        words = message.lower().split(" ")
        if nick == self.nickname:
            nickname = "*"
            sep = ">"
            message = f"<span foreground='grey'>{message}</span>"
        elif self.nickname.lower() in words or (self.nickname+":").lower() in words or ("@"+self.nickname).lower() in words:
            message = f"<span foreground='red'>{message}</span>"
        if nick == self.last_message_nick:
            nickname = ""
        iter = self.store.append([self.get_nick_markup(nickname), message, sep])
        path = self.store.get_path(iter)
        self.treeview.scroll_to_cell(path, None, False, 0.0, 0.0)
        self.last_message_nick = nick

    @idle
    def update_users(self):
        self.user_store.clear()
        users = self.client.channel_users[self.channel]
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        icon = Gtk.Image.new_from_icon_name("system-users-symbolic", Gtk.IconSize.MENU)
        box.pack_start(icon, True, True, 0)
        box.pack_start(Gtk.Label(label=len(users)), True, True, 0)
        column = self.user_treeview.get_column(0)
        column.set_widget(box)
        column.set_alignment(0.5)
        box.show_all()
        for user in users:
            self.user_store.append([self.get_nick_markup(user), user])

    @_async
    def connect_to_server(self):
        try:
            if self.tls:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                factory = Factory(wrapper=context.wrap_socket)
                self.client.connect(self.settings.get_string("server"),
                                    self.settings.get_int("port"),
                                    self.nickname, connect_factory=factory)
            else:
                self.client.connect(self.settings.get_string("server"),
                                    self.settings.get_int("port"),
                                    self.nickname)
            self.is_connected = True
            self.client.start()
        except Exception as e:
            self.show_error_status("dialog-error-symbolic", _("Error"), str(e))

app = IRCApp()
app.run()