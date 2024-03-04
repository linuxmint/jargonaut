def bind_entry_widget(widget, settings, key, fn_callback=None):
    widget.set_text(settings.get_string(key))
    widget.connect("changed", on_bound_entry_changed, settings, key, fn_callback)

def bind_switch_widget(widget, settings, key, fn_callback=None):
    widget.set_active(settings.get_boolean(key))
    widget.connect("notify::active", on_bound_switch_activated, settings, key, fn_callback)

def on_bound_entry_changed(widget, settings, key, fn_callback=None):
    settings.set_string(key, widget.get_text())
    if fn_callback is not None:
        fn_callback(widget.get_active())

def on_bound_switch_activated(widget, active, settings, key, fn_callback=None):
    settings.set_boolean(key, widget.get_active())
    if fn_callback is not None:
        fn_callback(widget.get_active())
