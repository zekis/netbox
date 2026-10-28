from netbox.plugins import PluginMenuItem

menu_items = (
    PluginMenuItem(
        link='plugins:netbox_drawing_canvas:drawing_list', link_text='Drawing sheets',
        permissions=['netbox_drawing_canvas.view_drawing'],
    ),
)
