import gi

import config
from source import VideoWallSource

gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import GObject, Gst, GstRtspServer

class MediaFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, width, height, rtsp_host, rtsp_username, rtsp_password):
        GstRtspServer.RTSPMediaFactory.__init__(self)

        self.canvas_width = width
        self.canvas_height = height

        self.rtsp_host = rtsp_host
        self.rtsp_username = rtsp_username
        self.rtsp_password = rtsp_password

    def do_create_element(self, url):
        source = VideoWallSource(
            self.canvas_width, self.canvas_height,
            self.rtsp_host, self.rtsp_username, self.rtsp_password
        )
        video_wall_bin = source.create_video_wall_bin("video_wall_bin")

        vaapih264enc = Gst.ElementFactory.make("vaapih264enc")

        h264parse = Gst.ElementFactory.make("h264parse")
        
        rtph264pay = Gst.ElementFactory.make("rtph264pay", "pay0")
        rtph264pay.set_property("config-interval", -1)

        # Create a pipeline that also does encoding and payloading.
        pipeline = Gst.Pipeline.new("pipeline")
        pipeline.add(video_wall_bin)
        pipeline.add(vaapih264enc)
        pipeline.add(h264parse)
        pipeline.add(rtph264pay)

        caps = Gst.Caps.from_string("video/x-raw,width=%d,height=%d,framerate=20/1" % (self.canvas_width, self.canvas_height))
        video_wall_bin.link_filtered(vaapih264enc, caps)
        vaapih264enc.link(h264parse)
        h264parse.link(rtph264pay)

        return pipeline

class Main:
    def __init__(self):
        # Load the configuration.
        self.config = config.get_config()

        # Initialize GStreamer.
        Gst.init(None)

        # Create a media factory.
        factory = MediaFactory(
            self.config['canvas']['width'],
            self.config['canvas']['height'],
            self.config['hikvision']['host'],
            self.config['hikvision']['username'],
            self.config['hikvision']['password']
        )
        factory.connect("media-configure", self.on_media_configure)
        factory.set_shared(True)

        # Make the server and provide it at the mount point.
        server = GstRtspServer.RTSPServer()
        server.set_auth(None)
        server.set_service(str(self.config['rtsp_server']['port']))
        server.connect("client-connected", self.on_client_connected)

        mount_points = server.get_mount_points()
        mount_points.add_factory(self.config['rtsp_server']['mount_point'], factory)

        server.attach(None)

        # Create the event loop and run.
        loop = GObject.MainLoop()
        try:
            loop.run()
        except:
            pass
    
    def on_client_connected(self, server, client):
        print("client %s connected" % (client.get_connection().get_ip()))

    def on_media_configure(self, factory, media):
        print("media_configure")
        print(factory)
        print(media)

if __name__ == '__main__':
    Main()
