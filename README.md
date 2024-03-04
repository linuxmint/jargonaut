# Jargonaut

Jargonaut is an easy to use Chat Room application.

It's an XAPP so it's designed to work on all Linux distributions and all desktop environments.

Under the hood it uses IRC, though it makes no difference from a user point of view. It doesn't act as an IRC client, only a chat room application.

# TODO 1.0

## rendering

- Switch to HTML/CSS
	- Add timestamps
	- Make links clickable
	- wordwrap
	- Put lines closer to one-another

## Other

- Connect to multiple channels
- Refactor OOP

# Todo 2.0

## Localization

- Check i18n
- Set up translations

## UI/Settings

- Design a better icon
- decouple default settings from mint values

## Rendering

- add a line to indicate where the last read message was
- Implement thumbs for pictures?

## Features

- support /me command
- ability to ignore users (probably means we need a unique way of IDing them as well)
- Implement a tray
- Notify the user when quoted
- Document the project scope (this isn't meant to be a full IRC client)
- Filter unwanted words
- Support DND of files (via pastebin) and images (via imgur)
- Implement spoiler tag
- Add inxi automation
- raise awareness that anything prior join isn't seen (i.e. noobs get the impression the room is dead)
- warn users not to leave if they do shortly after they asked a question
- don't autoscroll if the scrolledview isn't at the bottom
- spell check
- show nick changes
- show people who left if user interacted with them or if they spoke recently
- detect all caps message and suppress them
- Show what happened before join(), via a logger/bot?