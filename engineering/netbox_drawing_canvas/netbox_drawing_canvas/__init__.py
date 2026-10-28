from netbox.plugins import PluginConfig


class DrawingCanvasConfig(PluginConfig):
    name = 'netbox_drawing_canvas'
    verbose_name = 'Drawing Canvas'
    description = 'Tenant-scoped equipment drawing sheets'
    version = '0.1.0'
    base_url = 'drawing-canvas'
    min_version = '4.2.9'
    max_version = '4.7.4'


config = DrawingCanvasConfig
