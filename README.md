# Hikvision Video Wall

This project implements a video wall for use with Hikvision's 16-channel NVRs
that outputs H.264 streams. This was done because the channel zero encoding
functionality on the NVR itself was of very low quality.

## Requirements

- Linux (tested on Ubuntu 18.04 LTS)
- GStreamer
- Python 3
- An Intel GPU (tested on Kaby Lake)

## Instructions

These instructions are for Ubuntu 18.04 LTS.

    python -m venv .venv
    pip install -r requirements.txt
    vext -i .venv/gi.vext
    vim config.yml
    python rtsp_server.py

To test:

    gst-launch-1.0 rtspsrc "http://host:63000/stream" ! decodebin ! autovideosink
