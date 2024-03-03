project('jargonaut', version: '1.0.5')

i18n = import('i18n')

gettext_package = meson.project_name()

prefix = get_option('prefix')
datadir = get_option('datadir')

podir = meson.source_root() / 'po'

subdir('data')
subdir('po')
