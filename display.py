import ctypes
import sys

import gi

import config
from source import VideoWallSource

gi.require_version("Gst", "1.0")
from gi.repository import GObject, Gst

class Main:
    ctypes.cdll.LoadLibrary('libX11.so').XInitThreads()

    def __init__(self):
        # Load the configuration.
        self.config = config.get_config()

        # Initialize GStreamer and construct the pipeline.
        Gst.init(None)
        self.pipeline = self.construct_pipeline()
        self.pipeline.set_state(Gst.State.PAUSED)
        self.pipeline.set_state(Gst.State.PLAYING)

        # Create the event loop and run.
        self.loop = GObject.MainLoop()
        try:
            self.loop.run()
        except:
            pass
        
        self.pipeline.set_state(Gst.State.NULL)

    def construct_pipeline(self):
        canvas_width = self.config['canvas']['width']
        canvas_height = self.config['canvas']['height']
        rtsp_host = self.config['hikvision']['host']
        rtsp_username = self.config['hikvision']['username']
        rtsp_password = self.config['hikvision']['password']

        # Create the pipeline and the video wall bin.
        source = VideoWallSource(canvas_width, canvas_height, rtsp_host, rtsp_username, rtsp_password)
        self.bin = source.create_video_wall_bin("video_wall_bin")
        glimagesink = Gst.ElementFactory.make("glimagesink")
        glimagesink.set_property("max-lateness", 1000000000)
        glimagesink.set_property("ts-offset", 1000000000)

        pipeline = Gst.Pipeline.new("pipeline")
        pipeline.add(self.bin)
        pipeline.add(glimagesink)

        # Link up the pipeline.
        caps = Gst.Caps.from_string("video/x-raw(memory:GLMemory),width=%d,height=%d,framerate=20/1" % (canvas_width, canvas_height))
        self.bin.link_filtered(glimagesink, caps)

        # Listen to bus messages.
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)
        return pipeline
    
    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            sys.stdout.write("End of stream\n")
            self.loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            sys.stderr.write("Error: %s: %s\n" % (err, debug))
            self.loop.quit()
        elif t == Gst.MessageType.STATE_CHANGED:
            # change = message.parse_state_changed()
            # sys.stdout.write("%s State changed from %s -> %s\n" % (
            #     message.src.get_name(),
            #     change.oldstate.value_nick,
            #     change.newstate.value_nick
            # ))
            pass
        elif t == Gst.MessageType.STREAM_STATUS:
            status, owner = message.parse_stream_status()
            sys.stdout.write("%s Stream status changed to %s\n" % (owner.get_name(), status.value_nick))
        elif t == Gst.MessageType.NEED_CONTEXT:
            # ok, context_type = message.parse_context_type()
            # sys.stdout.write("%s Need context %s\n" % (message.src.get_name(), context_type))
            pass
        elif t == Gst.MessageType.QOS:
            live, running_time, stream_time, timestamp, duration = message.parse_qos()
            sys.stdout.write(
                "QOS: live=%s, running_time=%d, stream_time=%d, timestamp=%d, duration=%d\n" % (
                    live, running_time, stream_time, timestamp, duration))
        elif t == Gst.MessageType.TAG:
            taglist = message.parse_tag()
            sys.stdout.write("TAG: %s\n" % taglist.to_string())
        elif t == Gst.MessageType.NEW_CLOCK:
            clock = message.parse_new_clock()
            sys.stdout.write("New clock created: %s\n" % clock)
        elif t == Gst.MessageType.LATENCY:
            sys.stdout.write("Latency adjustment requested\n")
            self.bin.recalculate_latency()
        elif t == Gst.MessageType.HAVE_CONTEXT:
            context = message.parse_have_context()
            sys.stdout.write("Have context %s (%s)\n" % (context.get_context_type(), context.get_structure().to_string()))
        elif t == Gst.MessageType.ELEMENT:
            structure = message.get_structure()
            name = structure.get_name()
            if name == "GstNavigationMessage":
                event_structure = structure.get_value("event").get_structure()
                event = event_structure.get_value("event")
                if event == "key-release":
                    key = event_structure.get_value("key")
                    self.on_key_release(key)
        elif t == Gst.MessageType.PROGRESS:
            pass
        else:
            print(t)
        return True
    
    def on_key_release(self, key):
        if key == "d":
            sys.stdout.write("Dumping pipeline to file\n")
            Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "pipeline")        

if __name__ == '__main__':
    Main()
