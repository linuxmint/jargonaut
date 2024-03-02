# Jargonaut

Jargonaut is an easy to use Chat Room application.

It's an XAPP so it's designed to work on all Linux distributions and all desktop environments.

Under the hood it uses IRC, though it makes no difference from a user point of view. It doesn't act as an IRC client, only a chat room application.

# TODO

## rendering

- Switch to HTML/CSS
- Implement spoiler tag
- Add timestamps
- Make links clickable
- add a line in the treeview to indicate where the last read message was
- wordwrap
- Sup in nickname makes things harder to read
- Implement thumbs for pictures?
- Put lines closer to one-another

## UI/Settings

- Add an error page
- Design an icon
- Add a settings page
- decouple default settings from mint values

## Other

- Don't correlate unique suffix and color, use pre-determined colors which work well, based on who is read in which order (i.e. people will have different colors on different client instances, but that's ok)
- Connect to multiple channels
- Filter unwanted words
- Support DND of files (via pastebin) and images (via imgur)
- Implement a tray
- Notify the user when quoted
- Document the project scope (this isn't meant to be a full IRC client)
- support /me command
- ability to ignore users (probably means we need a unique way of IDing them as well)

## Localization

- Check i18n
- add keywords in the desktop file
- Set up translations
