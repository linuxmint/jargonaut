#!/usr/bin/python3

import gi
import irc.client
gi.require_version('Gtk', '3.0')
gi.require_version('XApp', '1.0')
from gi.repository import Gtk, Gio, GLib, Gdk, XApp, Pango
from irc.connection import Factory
import random
import threading
import getpass
import random
import re
import ssl
import gettext

color_palette = [
    "#E6194B",  # Rouge
    "#3CB44B",  # Vert
    "#FFE119",  # Jaune
    "#4363D8",  # Bleu
    "#F58231",  # Orange
    "#911EB4",  # Violet
    "#42D4F4",  # Cyan
    "#F032E6",  # Magenta
    "#BFEF45",  # Vert clair
    "#FABEBE",  # Rose
    "#469990",  # Vert d'eau
    "#E6BEFF",  # Lavande
    "#9A6324",  # Brun
    "#FFFAC8",  # Jaune pâle
    "#800000",  # Marron
    "#AAFFC3",  # Vert menthe
    "#808000",  # Olive
    "#FFD8B1",  # Pêche
    "#000075",  # Bleu marine
    "#A9A9A9"   # Gris
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
        print("Joined channel: " + event.target)
        self.print_info(f"Joined channel: target={event.target} source={event.source}")
        self.app.builder.get_object("main_stack").set_visible_child_name("page_chat")
        nick = event.source.nick
        channel = event.target
        if nick not in self.channel_users[channel]:
            self.app.assign_color(nick)
            self.channel_users[channel].append(nick)
            self.app.update_users()

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

    @idle
    def on_part(self, connection, event):
        self.print_info(f"Part: target={event.target} source={event.source}")
        nick = event.source.nick
        channel = event.target
        if nick in self.channel_users[channel]:
            self.channel_users[channel].remove(nick)
            self.app.update_users()

    def on_all_raw_messages(self, connection, event):
        self.print_info("Raw message: " + str(event.arguments))

    def on_pubmsg(self, connection, event):
        nick = event.source.split('!')[0]
        message = event.arguments[0]
        self.app.print_message(nick, message)

    def on_nicknameinuse(self, connection, event):
        self.print_error("Nickname in use")
        self.app.nickname =  self.app.get_new_nickname(with_random_suffix=True)
        self.app.assign_color(self.app.nickname)
        connection.nick(self.app.nickname)
        self.print_error("Nickname in use, trying with " + self.app.nickname)
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

        self.builder = Gtk.Builder()
        self.builder.add_from_file("/usr/share/jargonaut/jargonaut.ui")
        self.window = self.builder.get_object("main_window")
        self.window.set_application(self)
        self.window.show_all()

        self.treeview = self.builder.get_object("treeview_chat")
        self.store = Gtk.ListStore(str, str, str) # nick, message
        self.treeview.set_model(self.store)
        font_desc = Pango.FontDescription("Monospace")
        self.treeview.modify_font(font_desc)

        renderer = Gtk.CellRendererText()
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
        self.user_treeview.modify_font(font_desc)

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

        self.client = IRCClient(self)
        self.connect_to_server()

    def assign_color(self, nick):
        if nick not in self.user_colors.keys():
            self.user_colors[nick] = color_palette[self.color_index]
            self.color_index = (self.color_index + 1) % len(color_palette)

    def get_nick_markup(self, nick):
        color = self.user_colors[nick]
        nick = f"<span foreground='{color}'>{nick}</span>"
        return nick

    def get_new_nickname(self, with_random_suffix=False):
        if self.settings.get_string("nickname") != "":
            prefix = self.settings.get_string("nickname")
        else:
            prefix = getpass.getuser()
        if with_random_suffix:
            suffix = '{:02x}'.format(random.randint(0, 255))
            return f"{prefix}_{suffix}"
        else:
            return prefix

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
        iter = self.store.append([self.get_nick_markup(nick), message, "|"])
        path = self.store.get_path(iter)
        self.treeview.scroll_to_cell(path, None, False, 0.0, 0.0)

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
        self.client.start()

app = IRCApp()
app.run()