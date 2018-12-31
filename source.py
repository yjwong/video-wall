import math
import time

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

class CameraVideoSource:
    def __init__(self, rtsp_host, rtsp_username, rtsp_password, name, camera_id):
        self.rtsp_host = rtsp_host
        self.rtsp_username = rtsp_username
        self.rtsp_password = rtsp_password

        self.initialize_bin(name, camera_id)

    def initialize_bin(self, name, camera_id):
        # Make the pipeline elements.
        self.rtspsrc = Gst.ElementFactory.make("rtspsrc", "camera_%d_rtspsrc" % (camera_id))
        self.rtspsrc.set_property("location", "rtsp://%s/Streaming/Channels/%d02" % (self.rtsp_host, camera_id))
        self.rtspsrc.set_property("timeout", 0)
        self.rtspsrc.set_property("user-id", self.rtsp_username)
        self.rtspsrc.set_property("user-pw", self.rtsp_password)
        self.rtspsrc.set_property("drop-on-latency", True)
        self.rtspsrc.set_property("latency", 200)
        self.rtspsrc.set_property("protocols", "tcp")

        self.queue = Gst.ElementFactory.make("queue", "camera_%d_queue" % (camera_id))

        self.rtph264depay = Gst.ElementFactory.make("rtph264depay", "camera_%d_rtph264depay" % (camera_id))

        self.h264parse = Gst.ElementFactory.make("h264parse", "camera_%d_h264parse" % (camera_id))
        self.h264parse.set_property("config-interval", -1)

        self.vaapih264dec = Gst.ElementFactory.make("vaapih264dec", "camera_%d_vaapih264dec" % (camera_id))
        self.vaapih264dec.set_property("low-latency", True)

        self.vaapipostproc = Gst.ElementFactory.make("vaapipostproc", "camera_%d_vaapipostproc" % (camera_id))

        self.glupload = Gst.ElementFactory.make("glupload", "camera_%d_glupload" % (camera_id))

        self.glcolorconvert = Gst.ElementFactory.make("glcolorconvert", "camera_%d_glcolorconvert" % (camera_id))

        self.glcolorscale = Gst.ElementFactory.make("glcolorscale", "camera_%d_glcolorscale" % (camera_id))

        # Add all elements to the pipeline.
        self.bin = Gst.Bin.new(name)
        self.bin.add(self.rtspsrc)
        self.bin.add(self.glupload)
        self.bin.add(self.glcolorconvert)
        self.bin.add(self.glcolorscale)

        # Create a dummy gltestsrc before the RTSP pad becomes available.
        self.gltestsrc = Gst.ElementFactory.make("gltestsrc", "camera_%d_gltestsrc" % (camera_id))
        self.gltestsrc.set_property("is-live", True)
        self.bin.add(self.gltestsrc)

        # Link them up.
        self.rtspsrc.connect("pad-added", self.on_pad_added)
        self.gltestsrc.link(self.glupload)
        self.glupload.link(self.glcolorconvert)
        self.glcolorconvert.link(self.glcolorscale)

        # Create a ghost pad at the end of the bin.
        self.src_pad = Gst.GhostPad.new("src", self.glcolorscale.get_static_pad("src"))
        self.bin.add_pad(self.src_pad)

    def on_pad_added(self, rtspsrc, pad):
        # Block the rtspsrc pad because rtspsrc is not linked yet.
        pad.add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, self.on_rtspsrc_pad_blocked)
    
    def on_rtspsrc_pad_blocked(self, pad, info):
        time.sleep(0.5)

        # Stop gltestsrc in preparation for disconnection from glupload.
        self.gltestsrc.set_state(Gst.State.NULL)
        self.gltestsrc.unlink(self.glupload)
        self.bin.remove(self.gltestsrc)

        # Remove the probe.
        pad.remove_probe(info.id)

        # Hook the new pipeline in.
        self.bin.add(self.queue)
        self.bin.add(self.rtph264depay)
        self.bin.add(self.h264parse)
        self.bin.add(self.vaapih264dec)
        self.bin.add(self.vaapipostproc)

        self.rtspsrc.link(self.queue)
        self.queue.link(self.rtph264depay)
        self.rtph264depay.link(self.h264parse)
        self.h264parse.link(self.vaapih264dec)
        self.vaapih264dec.link(self.vaapipostproc)
        self.vaapipostproc.link(self.glupload)

        # Make sure the elements are in the right state.
        self.queue.sync_state_with_parent()
        self.rtph264depay.sync_state_with_parent()
        self.h264parse.sync_state_with_parent()
        self.vaapih264dec.sync_state_with_parent()
        self.vaapipostproc.sync_state_with_parent()

        return Gst.PadProbeReturn.OK

class VideoWallSource:
    def __init__(self, width, height, rtsp_host, rtsp_username, rtsp_password):
        self.canvas_width = width
        self.canvas_height = height

        self.rtsp_host = rtsp_host
        self.rtsp_username = rtsp_username
        self.rtsp_password = rtsp_password

    def create_video_wall_bin(self, name):
        # Create the elements for the bin.
        mixer = Gst.ElementFactory.make("glvideomixer")
        
        # Create the bin.
        bin = Gst.Bin.new(name)
        bin.add(mixer)

        # Create the camera bins and link them up too.
        for i in range(0, 16):
            camera_id = i + 1
            x, y, width, height = self.get_position_params_for_camera(camera_id)

            camera_bin = self.create_bin_for_camera("camera_bin_%d" % camera_id, camera_id)

            mixer_pad_template = mixer.get_pad_template("sink_%u")
            mixer_pad = mixer.request_pad(mixer_pad_template)
            mixer_pad.set_property("xpos", x)
            mixer_pad.set_property("ypos", y)

            bin.add(camera_bin)

            # Hook the bin up to the mixer.
            caps = Gst.Caps.from_string("video/x-raw(memory:GLMemory),width=%d,height=%d" % (width, height))
            camera_bin.link_filtered(mixer, caps)

        # Create a ghost pad at the end of the bin.
        src_pad = Gst.GhostPad.new("src", mixer.get_static_pad("src"))
        bin.add_pad(src_pad)

        return bin

    def create_bin_for_camera(self, name, camera_id):
        videosrc = CameraVideoSource(self.rtsp_host, self.rtsp_username, self.rtsp_password, name, camera_id)
        return videosrc.bin

    def get_position_params_for_camera(self, camera_id):
        items_per_row = 4
        row = math.floor((camera_id - 1) / items_per_row)
        col = (camera_id - 1) % items_per_row
        return (
            col * self.canvas_width / items_per_row,
            row * self.canvas_height / items_per_row,
            self.canvas_width / items_per_row,
            self.canvas_height / items_per_row
        )
