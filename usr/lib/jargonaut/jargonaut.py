#!/usr/bin/python3

import gi
import irc.client
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, Gdk
from irc.connection import Factory
import random
import threading
import getpass
import random
import re
import ssl

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

def generate_username():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    color = '{:02x}{:02x}{:02x}'.format(r, g, b)
    return f"{getpass.getuser()}_{color}"

def get_markup_from_nick(nick):
    color = "#000000"
    if "_" in nick:
        prefix = nick.split("_")[0]
        suffix = nick.split("_")[1]
        if re.fullmatch(r"[0-9a-fA-F]{6}", suffix) is not None:
            # suffix is a valid RGB code
            color = "#" + suffix
            nick = f"<span foreground='{color}'>{prefix} <sup>{suffix}</sup></span>"
    return nick

def is_valid_rgb(color):
    match = re.fullmatch(r"#[0-9a-fA-F]{6}", color)
    return match is not None

class IRCClient(irc.client.SimpleIRCClient):
    def __init__(self, app):
        irc.client.SimpleIRCClient.__init__(self)
        self.app = app
        self.channel_users = {}

    def on_welcome(self, connection, event):
        connection.join("#minttest")
        connection.names(["#minttest"])

    @idle
    def on_join(self, connection, event):
        print("Joined channel: " + event.target)
        self.print_info(f"Joined channel: target={event.target} source={event.source}")
        self.app.builder.get_object("main_stack").set_visible_child_name("page_chat")
        nick = event.source.nick
        self.app.user_store.append([get_markup_from_nick(nick), nick])

    def on_namreply(self, connection, event):
        channel = event.arguments[1]
        users = event.arguments[2].split()
        self.channel_users[channel] = users
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
        new_nickname =  generate_username()
        connection.nick(new_nickname)
        self.print_error("Nickname in use, trying with " + new_nickname)
        self.app.builder.get_object("label_username").set_markup(get_markup_from_nick(new_nickname))
        self.app.nickname = new_nickname

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

        self.last_key_press_is_tab = False

        self.builder = Gtk.Builder()
        self.builder.add_from_file("/usr/share/jargonaut/jargonaut.ui")
        self.window = self.builder.get_object("main_window")
        self.window.set_application(self)
        self.window.show_all()

        self.treeview = self.builder.get_object("treeview_chat")
        self.store = Gtk.ListStore(str, str) # nick, message
        self.treeview.set_model(self.store)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("", renderer, markup=0)
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

        self.nickname =  generate_username()
        self.builder.get_object("label_username").set_markup(get_markup_from_nick(self.nickname))

        self.client = IRCClient(self)
        self.connect_to_server()

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == "Tab":
            text = widget.get_text()
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
        elif keyname == "Return":
            self.last_key_press_is_tab = False
            message = widget.get_text().strip()
            if message != "":
                completion = widget.get_completion()
                widget.set_completion(None)
                widget.set_text("")
                widget.set_completion(completion)
                self.print_message(self.nickname, message)
                self.send_message(message)
            return True
        else:
            self.last_key_press_is_tab = False
            return False

    def do_startup(self):
        Gtk.Application.do_startup(self)

    @_async
    def send_message(self, message):
        self.client.connection.privmsg("#minttest", message)

    @idle
    def print_message(self, nick, message):
        # Format text (IRC codes -> pango)
        message = re.sub(r'\x02(.*?)\x02', r'<b>\1</b>', message)
        message = re.sub(r'\x1D(.*?)\x1D', r'<i>\1</i>', message)
        message = re.sub(r'\x1F(.*?)\x1F', r'<u>\1</u>', message)
        message = re.sub(r'\x1E(.*?)\x1E', r'<s>\1</s>', message)
        iter = self.store.append([get_markup_from_nick(nick), message])
        path = self.store.get_path(iter)
        self.treeview.scroll_to_cell(path, None, False, 0.0, 0.0)


    @idle
    def update_users(self):
        self.user_store.clear()
        for user in self.client.channel_users["#minttest"]:
            self.user_store.append([get_markup_from_nick(user), user])

    @_async
    def connect_to_server(self):
        factory = Factory(wrapper=ssl.SSLContext(ssl.PROTOCOL_TLS).wrap_socket)
        self.client.connect("irc.spotchat.org", 6697, self.nickname, connect_factory=factory)
        self.client.start()

app = IRCApp()
app.run()