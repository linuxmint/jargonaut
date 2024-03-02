# Jargonaut

Jargonaut is an easy to use Chat Room application.

It's an XAPP so it's designed to work on all Linux distributions and all desktop environments.

Under the hood it uses IRC, though it makes no difference from a user point of view. It doesn't act as an IRC client, only a chat room application.

# TODO

- Set up translations
- Connect to multiple channels
- Make the IRC info (server, channels) configurable in gsettings
- Allow text format in the enty (bold, italic..etc)
- Support DND of files (via pastebin) and images (via imgur)
- Filter unwanted words
- Nicknames auto-completion
- Show the list of users in the room and a number of people connected
- Add an error page
- Design an icon
- Set up the GTKApplication as a singleton
- Implement a tray
- Notify the user when quoted
- Add a settings page
- Add timestamps
- Document the project scope (this isn't meant to be a full IRC client)
- Make links clickable
- Implement thumbs for pictures?
- Implement spoiler tag
- Let user choose nickname (vs username)
- Don't correlate unique suffix and color, use pre-determined colors which work well, based on who is read in which order (i.e. people will have different colors on different client instances, but that's ok)
- Put lines closer to one-another
- Sup in nickname makes things harder to read
- wordwrap
- support /me command
- add a line in the treeview to indicate where the last read message was
- add keywords in the desktop file
- ability to ignore users (probably means we need a unique way of IDing them as well)
- dark mode