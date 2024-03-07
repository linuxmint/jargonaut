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

## BETA

- Check i18n
- Set up translations
- Document the project scope (this isn't meant to be a full IRC client)
- Design a better icon
- decouple default settings from mint values
- add a line to indicate where the last read message was
- ability to ignore users (probably means we need a unique way of IDing them as well)
- Filter unwanted words
- Support DND of files (via pastebin) and images (via imgur)
- Implement spoiler tag
- raise awareness that anything prior join isn't seen (i.e. noobs get the impression the room is dead)
- don't autoscroll if the scrolledview isn't at the bottom
- spell check
- detect all caps message and suppress them
- Show what happened before join(), via a logger/bot?
- disable thumbs by default
- Add inxi automation
- improve autocompletion for nicknames (it should work when you say hi at least..)
- support pastebin preview?
- wait for view to be loaded before autoscroll
- regex for img should support svg, bmp, webp
- regex for domains should be smarter or include .cc, .io..etc.