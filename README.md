# Jargonaut

Jargonaut is an easy to use Chat Room application.

It's an XAPP so it's designed to work on all Linux distributions and all desktop environments.

Under the hood it uses IRC, though it makes no difference from a user point of view. It doesn't act as an IRC client, only a chat room application.

# TODO

## ALPHA

- Add timestamps
- Connect to multiple channels
- show nick changes
- show people who left if user interacted with them or if they spoke recently

## Integration

- Check i18n
- Set up translations
- Document the project scope (this isn't meant to be a full IRC client)
- decouple default settings from mint values
- raise awareness that anything prior join isn't seen (i.e. noobs get the impression the room is dead), assistant

# Security / Privacy / Moderation

- disable thumbs by default
- Filter unwanted words

## BETA

- ability to ignore users (probably means we need a unique way of IDing them as well)
- don't autoscroll if the scrolledview isn't at the bottom
- improve autocompletion for nicknames (it should work when you say hi at least..)
- wait for view to be loaded before autoscroll
- make not quitting on window close optional

## Features relying on upload

- Add inxi automation
- Add img DND
- Add buffer pastebin/imagebin

## Distant future

- spell check
- Show what happened before join(), via a logger/bot?
- detect all caps message and suppress them
- add a line to indicate where the last read message was
