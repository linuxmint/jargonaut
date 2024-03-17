#!/usr/bin/python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gspell', '1')
gi.require_version('Notify', '0.7')
try:
    gi.require_version('WebKit2', '4.1')
except:
    gi.require_version('WebKit2', '4.0')
gi.require_version('XApp', '1.0')
from gi.repository import Gtk, Gio, GLib, Gdk, Notify, WebKit2, XApp, Gspell
import irc.client
import getpass
import gettext
import html
import locale
import os
import random
import re
import setproctitle
import ssl
import webbrowser
from irc.connection import Factory
from settings import bind_entry_widget, bind_switch_widget
from ui import build_menu, idle, _async, color_palette, format_timespan, get_span_minutes

# i18n
APP = "jargonaut"
LOCALE_DIR = "/usr/share/locale"
locale.bindtextdomain(APP, LOCALE_DIR)
gettext.bindtextdomain(APP, LOCALE_DIR)
gettext.textdomain(APP)
_ = gettext.gettext

setproctitle.setproctitle("jargonaut")
Notify.init(_("Chat Room"))

class Message():
    def __init__(self, nick, text, action=None, old_nick=None, separator=False):
        self.nick = nick
        self.text = text
        self.time = GLib.DateTime.new_now_local()
        self.action = action
        self.old_nick = old_nick
        self.separator = separator

class App(Gtk.Application):
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
        self.show_thumbs = self.settings.get_boolean("show-thumbs")
        self.nickname = self.get_new_nickname()

        self.channel_users = {}
        self.channel_users[self.channel] = []
        self.messages = []
        self.n_real_messages = 0
        self.scrollback_queue_start_count = 0
        self.separator_message = None

        prefer_dark_mode = self.settings.get_boolean("prefer-dark-mode")
        try:
            # DarkModeManager is available in XApp 2.6+
            self.dark_mode_manager = XApp.DarkModeManager.new(prefer_dark_mode)
        except:
            print("XAppDarkModeManager not available, using Gtk.Settings")
            # Use the Gtk.Settings API as a fallback for older versions
            Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", prefer_dark_mode)

        self.last_key_press_is_tab = False
        self.last_message_nick = ""

        self.builder = Gtk.Builder()
        self.builder.add_from_file("/usr/share/jargonaut/jargonaut.ui")
        self.window = self.builder.get_object("main_window")
        self.window.set_application(self)
        self.window.connect("delete_event", self.close_window)
        self.window.show()

        css_provider = Gtk.CssProvider()
        css_provider.load_from_path("/usr/share/jargonaut/style.css")
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Users button
        self.builder.get_object("users_button").connect("clicked", self.on_users_button_clicked)
        self.builder.get_object("back_button").connect("clicked", self.on_back_button_clicked)

        # Tray
        menu = Gtk.Menu()
        image = Gtk.Image.new_from_icon_name("application-exit-symbolic", Gtk.IconSize.MENU)
        menuItem = Gtk.ImageMenuItem(label=_("Quit"), image=image)
        menuItem.connect('activate', self.on_tray_quit)
        menu.append(menuItem)
        menu.show_all()
        self.tray = XApp.StatusIcon()
        self.tray.set_secondary_menu(menu)
        self.tray.set_icon_name("jargonaut-status-normal-symbolic")
        self.tray.set_tooltip_text(_("Chat Room"))
        self.tray.set_visible(True)
        self.tray.connect('activate', self.on_tray_activated)

        # Menubar
        menu = self.builder.get_object("main_menu")
        build_menu(self, self.window, menu)

        self.main_stack = self.builder.get_object("main_stack")

        # Settings widgets

        bind_switch_widget(self.builder.get_object("pref_dark"), self.settings, "prefer-dark-mode", fn_callback=self.update_dark_mode)
        bind_switch_widget(self.builder.get_object("pref_24h"), self.settings, "timestamp-24h", fn_callback=self.update_timestamp_format)

        bind_entry_widget(self.builder.get_object("pref_nickname"), self.settings, "nickname", fn_callback=self.show_restart_infobar)
        bind_entry_widget(self.builder.get_object("pref_password"), self.settings, "password", fn_callback=self.show_restart_infobar),
        bind_switch_widget(self.builder.get_object("pref_acceleration"), self.settings, "hw-acceleration", fn_callback=self.update_hw_acceleration)
        bind_switch_widget(self.builder.get_object("show_thumbs"), self.settings, "show-thumbs", fn_callback=self.update_show_thumbs)

        self.webview = WebKit2.WebView()
        self.update_hw_acceleration(self.settings.get_boolean("hw-acceleration"))
        self.webview.connect("decide-policy", self.on_decide_policy)
        self.webview.show()
        self.render_html()

        self.builder.get_object("webview_box").pack_start(self.webview, True, True, 0)

        self.scrollback_return_button = self.builder.get_object("scrollback_return_button")
        self.scrollback_return_button.connect("clicked", self.on_scrollback_return_button_clicked)

        self.user_treeview = self.builder.get_object("treeview_users")
        self.user_store = Gtk.ListStore(str, str) # nick, raw_nick
        self.user_treeview.set_model(self.user_store)
        self.user_store.set_sort_column_id(1, Gtk.SortType.ASCENDING)

        self.user_list_box = self.builder.get_object("user_list_box")
        self.user_list_box.set_visible(self.settings.get_boolean("user-list-visible"))
        self.current_paned_position = 0


        self.chat_paned = self.builder.get_object("chat_paned")

        completion = Gtk.EntryCompletion()
        completion.set_model(self.user_store)
        completion.set_text_column(1)
        completion.set_inline_completion(True)
        completion.set_popup_completion(True)

        self.entry = self.builder.get_object("entry_main")
        self.entry.set_completion(completion)
        self.entry.connect("key-press-event", self.on_key_press_event)

        checker = Gspell.Checker()
        language = Gspell.Language.lookup("en_US")
        checker.set_language(language)
        buffer = Gspell.EntryBuffer.get_from_gtk_entry_buffer(self.entry.get_buffer())
        buffer.set_spell_checker(checker)
        gspell_entry = Gspell.Entry.get_from_gtk_entry(self.entry)
        gspell_entry.set_inline_spell_checking(True)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("Users", renderer, markup=0)
        self.user_treeview.append_column(col)

        self.assign_color(self.nickname)
        self.builder.get_object("label_username").set_markup(self.nickname)

        self.client = irc.client.SimpleIRCClient()
        self.client.connection.add_global_handler("welcome", self.on_welcome)
        self.client.connection.add_global_handler("join", self.on_join)
        self.client.connection.add_global_handler("namreply", self.on_namreply)
        self.client.connection.add_global_handler("notice", self.on_notice)
        self.client.connection.add_global_handler("nick", self.on_nick)
        self.client.connection.add_global_handler("quit", self.on_quit)
        self.client.connection.add_global_handler("part", self.on_part)
        self.client.connection.add_global_handler("all_raw_messages", self.on_all_raw_messages)
        self.client.connection.add_global_handler("pubmsg", self.on_pubmsg)
        self.client.connection.add_global_handler("erroneusnickname", self.on_erroneusnickname)
        self.client.connection.add_global_handler("disconnect", self.on_disconnect)
        self.client.connection.add_global_handler("error", self.on_error)
        self.client.connection.add_global_handler("nicknameinuse", self.on_nicknameinuse)

        if os.environ.get("JARGONAUT_NO_SERVER_TEST", False):
            self.main_stack.set_visible_child_name("page_chat")
        else:
            self.connect_to_server()

#########################
# Nickname/user functions
#########################

    def assign_color(self, nick):
        if nick not in self.user_colors.keys():
            color = color_palette[self.color_index]
            print(f"Assigning color {color} to {nick}")
            self.user_colors[nick] = color
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
            prefix = prefix[:13] # 13 chars max + 3 chars for suffix
            suffix = '{:02x}'.format(random.randint(0, 255))
            return f"{prefix}_{suffix}"
        else:
            return prefix[:16] # 16 chars max

#####################
# IRC commands
#####################

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

    @_async
    def join_channels(self, connection):
        connection.join(self.channel)
        connection.names([self.channel])

    @_async
    def identify(self, connection):
        username = self.settings.get_string("nickname")
        password = self.settings.get_string("password")
        if username != "" and password != "":
            self.print_info(f"Identifying as {username}...")
            connection.privmsg("Nickserv", f"IDENTIFY {username} {password}")

    @_async
    def send_message(self, message):
        message = message.replace('\x16', '\x1D')
        self.client.connection.privmsg(self.channel, message)

    @_async
    def disconnect(self):
        try:
            self.client.connection.disconnect(message=_("Jargonaut signing out!"))
        except Exception as e:
            print(e)

#####################
# IRC signal handlers
#####################

    @idle
    def on_welcome(self, connection, event):
        self.join_channels(connection)

    @idle
    def on_join(self, connection, event):
        self.print_info(f"Joined channel: target={event.target} source={event.source}")
        nick = event.source.nick
        channel = event.target
        if nick not in self.channel_users[channel]:
            self.assign_color(nick)
            self.channel_users[channel].append(nick)
            self.update_users()
        if nick == self.nickname:
            self.builder.get_object("main_stack").set_visible_child_name("page_chat")
            self.entry.grab_focus()
            self.identify(connection)
        else:
            message = Message(nick, None, "join")
            self.messages.append(message)
            self.render_html()

    @idle
    def on_namreply(self, connection, event):
        channel = event.arguments[1]
        users = event.arguments[2].split()
        for user in users:
            for character in ["~", "&", "@", "%", "+"]:
                if user.startswith(character):
                    user = user[1:]
                    break
            self.assign_color(user)
            if not user in self.channel_users[channel]:
                self.channel_users[channel].append(user)
        self.update_users()

    @idle
    def on_notice(self, connection, event):
        self.print_info("Notice: " + event.source + " " + event.arguments[0])

    @idle
    def on_nick(self, connection, event):
        self.print_info(f"Nick: target={event.target} source={event.source}")
        old_nick = event.source.nick
        new_nick = event.target
        if old_nick in self.channel_users[self.channel]:
            self.channel_users[self.channel].remove(old_nick)
        if not new_nick in self.channel_users[self.channel]:
            self.channel_users[self.channel].append(new_nick)
        if not new_nick in self.user_colors.keys():
            self.assign_color(new_nick)
        if old_nick == self.nickname:
            self.nickname = new_nick
            self.builder.get_object("label_username").set_markup(new_nick)
        self.update_users()

        if new_nick != self.nickname:
            message = Message(new_nick, None, "nick", event.source.nick)
            self.messages.append(message)
            self.render_html()

    @idle
    def on_quit(self, connection, event):
        self.print_info(f"Quit: target={event.target} source={event.source}")
        nick = event.source.nick
        channel = event.target
        if nick in self.channel_users[self.channel]:
            self.channel_users[self.channel].remove(nick)
            self.update_users()

        if nick != self.nickname:
            message = Message(nick, None, "quit")
            self.messages.append(message)
            self.render_html()

    @idle
    def on_part(self, connection, event):
        self.print_info(f"Part: target={event.target} source={event.source}")
        nick = event.source.nick
        channel = event.target
        if nick in self.channel_users[channel]:
            self.channel_users[channel].remove(nick)
            self.update_users()

        if nick != self.nickname:
            message = Message(nick, None, "quit")
            self.messages.append(message)
            self.render_html()

    @idle
    def on_all_raw_messages(self, connection, event):
        if self.settings.get_boolean("debug"):
            content = str(event.arguments)
            self.print_info("Raw message: " + content)
            # Actions (i.e. /me commands) are not received as PRIVMSGS or PUBMSGS
            # only as RAW messages, so we need to handle them here
            if f"PRIVMSG {self.channel}" in content:
                if "\\x01ACTION" in content:
                    nick = content.split("!")[0].split(":")[1]
                    text = content.split("\\x01ACTION")[1].split("\\x01")[0]
                    text = f"\x01ACTION{text}\x01"
                    self.print_message(nick, text)

    @idle
    def on_pubmsg(self, connection, event):
        nick = event.source.split('!')[0]
        message = event.arguments[0]
        self.print_message(nick, message)

    @idle
    def on_erroneusnickname(self, connection, event):
        self.print_info("Invalid nickname: %s" % event.arguments[0])
        self.show_error_status("dialog-error-symbolic", _("Invalid nickname"), _("Your nickname was rejected. Restart the application to reset it."))
        self.settings.set_string("nickname", "")

    @idle
    def on_disconnect(self, connection, event):
        self.print_info("Disconnected from server: %s" % event.target)
        self.show_error_status("dialog-error-symbolic", _("Disconnected"), _("You have been disconnected from the server. Please try to reconnect."))

    @idle
    def on_error(self, connection, event):
        self.print_info("Error from server: %s" % event.arguments[0])
        self.show_error_status("dialog-error-symbolic", _("Error"), _("An error occurred: ") + event.arguments[0])

    @idle
    def on_nicknameinuse(self, connection, event):
        self.nickname =  self.get_new_nickname(with_random_suffix=True)
        self.assign_color(self.nickname)
        connection.nick(self.nickname)
        self.print_info(f"Nickname in use, switching to '{self.nickname}'")
        self.builder.get_object("label_username").set_markup(self.nickname)

##################
# UI IRC functions
##################

    def render_if_current(self):
        script = """
            ({
                page_height:      document.body.scrollHeight,
                current_position: document.body.scrollTop,
                viewport_height:  window.innerHeight
            });
        """
        self.webview.evaluate_javascript(script, -1, None, None, None, self.on_position_query_finished)

    def on_position_query_finished(self, webview, result, user_data=None):
        jscvalue = webview.evaluate_javascript_finish(result)
        if jscvalue is not None and jscvalue.is_object():
            page_height = jscvalue.object_get_property("page_height").to_double()
            current_position = jscvalue.object_get_property("current_position").to_double()
            viewport_height = jscvalue.object_get_property("viewport_height").to_double()

            if current_position + viewport_height >= page_height - 10:
                self.scrollback_return_button.hide()
                self.scrollback_queue_start_count = 0
                self._real_render_html()
            else:
                if self.scrollback_queue_start_count == 0 and self.messages[-1].action is None:
                    self.scrollback_queue_start_count = self.n_real_messages - 1

                    if self.separator_message is not None:
                        self.messages.remove(self.separator_message)

                    message = Message(None, None, separator=True)
                     # We're already handling a message (which was already appended),
                     # place this before it.
                    self.messages.insert(-1, message)
                    self.separator_message = message

                queued_count = self.n_real_messages - self.scrollback_queue_start_count
                if queued_count > 0:
                    self.scrollback_return_button.show()
                    button_text = gettext.ngettext(_("%d new message"), _("%d new messages"), queued_count) % (queued_count)
                    self.scrollback_return_button.set_label(button_text)

    def render_html(self):
        self.render_if_current()

    def _real_render_html(self):
        messages_section = "<div>"
        last_nick = ""
        last_message_time = None
        minutes_since_previous_message = 0
        for message in self.messages:
            if last_message_time is not None:
                minutes_since_previous_message = get_span_minutes(message.time, last_message_time)
            last_message_time = message.time
            date = format_timespan(message.time, self.settings.get_boolean("timestamp-24h"))
            mine = ""
            response = ""
            nickname = message.nick

            if message.text is not None:
                text = message.text
                words = text.lower().split(" ")
                if text.startswith("\x01ACTION") and text.endswith("\x01"):
                    text = text.replace("\x01ACTION", "").replace("\x01", "")
                    text = f"<i><-- {text}</i>"
                if message.nick == self.nickname:
                    mine = "mine"
                elif self.nickname.lower() in words or (self.nickname+":").lower() in words or ("@"+self.nickname).lower() in words:
                    response = "response"

            if message.action is not None:
                if message.action == "join":
                    action_message = _(f"{nickname} joined the channel")
                elif message.action == "quit":
                    action_message = _(f"{nickname} left the channel")
                elif message.action == "nick":
                    action_message = _(f"{message.old_nick} is now {nickname}")

                messages_section += f"""
                    <div class="action">
                        <div class="action-text">{action_message}</div>
                    </div>
                """
            elif message.separator:
                messages_section += f"""
                    <hr class="solid">
                """
            elif message.nick == last_nick and minutes_since_previous_message < 5:
                messages_section += f"""
                        <div class="line {response}">{text}</div>
                    """
            else:
                letter = nickname[0].upper()
                color = self.user_colors[nickname]
                messages_section += f"""
                    </div>
                    <div class="messages {mine}">
                        <span class="avatar"><span style="background-color:{color}">{letter}</span></span>
                        <div class="nick">{nickname}<span class="date">{date}</span></div>
                        <div class="line {response}">{text}</div>
                    """
            # ignore parts/joins with respect to chat continuity
            if message.action is None and not message.separator:
                last_nick = message.nick

        html = f"""
            <html>
            <head>
                <link rel="stylesheet" type="text/css" href="webview.css">
            </head>
            <body>
                {messages_section}
                </div>
                <script>
                    window.scrollTo(0, document.body.scrollHeight);
                </script>
            </body>
            </html>
        """

        self.webview.load_html(html, "file:///usr/share/jargonaut/")

    def is_image_url(self,url):
        image = url.split('/')[-1]
        image = image.split('?')[0]
        if image.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp')):
            return True

    @idle
    def print_message(self, nick, text):
        # Escape any tags, i.e. show exactly what people typed, don't let Webkit interpret it.
        text = html.escape(text)
        # Format text (IRC codes -> pango/HTML)
        text = re.sub(r'\x02(.*?)\x02', r'<b>\1</b>', text)
        text = re.sub(r'\x16(.*?)\x16', r'<i>\1</i>', text)
        text = re.sub(r'\x1D(.*?)\x1D', r'<i>\1</i>', text)
        text = re.sub(r'\x1F(.*?)\x1F', r'<u>\1</u>', text)
        text = re.sub(r'\x1E(.*?)\x1E', r'<s>\1</s>', text)
        # Convert URLs to clickable links
        url_pattern = r'((http[s]?://[^\s]{3,}\.[^\s]{2,}))'
        def repl(match):
            url = match.group(1)
            if self.is_image_url(url) and self.show_thumbs:
                return f'<a href="{url}"><img class="thumb" src="{url}" title="{url}"/></a>'
            else:
                return f'<a href="{url}">{url}</a>'
        text = re.sub(url_pattern, repl, text)

        message = Message(nick, text)
        self.messages.append(message)
        self.n_real_messages += 1
        self.render_html()
        self.last_message_nick = nick

        words = text.lower().split(" ")
        if self.nickname.lower() in words or (self.nickname+":").lower() in words or ("@"+self.nickname).lower() in words:
            if not self.is_window_focused():
                self.tray.set_icon_name("jargonaut-status-msg-symbolic")
                title = _("Message from %s") % message.nick
                self.send_notification(title, text)

    @idle
    def update_users(self):
        self.user_store.clear()
        users = self.channel_users[self.channel]
        self.builder.get_object("users_label").set_text(str(len(users)))
        for user in users:
            self.user_store.append([self.get_nick_markup(user), user])

    @idle
    def print_info(self, message):
        print("Info: " + message)

    @idle
    def show_error_status(self, icon_name, message, details):
        self.builder.get_object("main_stack").set_visible_child_name("page_status")
        self.builder.get_object("status_icon").set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        self.builder.get_object("status_label").set_text(message)
        self.builder.get_object("status_details").set_text(details)

###############
# App functions
###############

    def on_decide_policy(self, view, decision, decision_type):
        if decision_type == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            navigation_action = decision.get_navigation_action()
            if navigation_action.get_mouse_button() == 0:
                return False
            uri = decision.get_request().get_uri()
            webbrowser.open(uri)
            decision.ignore()
            return True
        return False

    def on_scrollback_return_button_clicked(self, widget):
        self.scrollback_return_button.hide()
        self.scrollback_queue_start_count = 0
        self._real_render_html()

    def close_window(self, window, event):
        window.hide()
        return True

    def send_notification(self, title, text):
        # We use self.notification (instead of just a variable) to keep a memory pointer
        # on the notification. Without doing this, callbacks are never executed by Gtk/Notify.
        self.notification = Notify.Notification.new(title, text, "jargonaut-status-msg-symbolic")
        self.notification.set_urgency(2)
        self.notification.set_timeout(Notify.EXPIRES_NEVER)
        self.notification.connect("closed", self.on_notification_closed)
        self.notification.show()

    def on_notification_closed(self, notification):
        self.tray.set_icon_name("jargonaut-status-normal-symbolic")
        self.window.show()
        self.window.present()

    def on_tray_quit(self, widget):
        self.quit()

    def is_window_focused(self):
        focused = False
        try:
            focused = self.window.get_window().get_state() & Gdk.WindowState.FOCUSED
        except:
            focused = self.window.is_active() and self.window.get_visible()
        return focused

    def on_back_button_clicked(self, widget):
        self.builder.get_object("main_stack").set_visible_child_name("page_chat")
        self.builder.get_object("back_button").set_visible(False)
        self.entry.grab_focus()

    def on_users_button_clicked(self, widget):
        visible = self.user_list_box.get_visible()
        self.settings.set_boolean("user-list-visible", not visible)
        self.user_list_box.set_visible(not visible)

    def on_tray_activated(self, icon, button, time):
        if button == Gdk.BUTTON_PRIMARY:
            self.tray.set_icon_name("jargonaut-status-normal-symbolic")
            if self.is_window_focused():
                self.window.hide()
            else:
                self.window.show()
                self.window.present_with_time(time)

    def update_hw_acceleration(self, active):
        settings = self.webview.get_settings()
        if active:
            policy = WebKit2.HardwareAccelerationPolicy.ALWAYS
        else:
            policy = WebKit2.HardwareAccelerationPolicy.NEVER
        settings.set_hardware_acceleration_policy(policy)
        self.show_restart_infobar()

    def update_show_thumbs(self, active):
            self.show_thumbs = True if active else False

    @idle
    def update_dark_mode(self, active):
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", active)

    def update_timestamp_format(self, active):
        self.render_html()

    def show_restart_infobar(self, *args, **kargs):
        # avoid showing the info bar during init
        if self.main_stack.get_visible_child_name() != "page_settings":
            return

        self.builder.get_object("prefs_restart_infobar").show()

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
        if keyname == "Return" or keyname == "KP_Enter":
            message = text.strip()
            if message != "":
                completion = widget.get_completion()
                widget.set_completion(None)
                widget.set_text("")
                widget.set_completion(completion)
                if message.startswith("/me "):
                    local_msg = message.replace("/me ", self.nickname + " ", 1)
                    remote_msg = message.replace("/me ", " ", 1)
                    remote_msg = f"\x01ACTION{remote_msg}\x01"
                    self.print_message(self.nickname, local_msg)
                    self.send_message(remote_msg)
                else:
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

    def do_shutdown(self):
        if self.is_connected:
            self.disconnect()

        Gtk.Application.do_shutdown(self)

app = App()
app.run()