import subprocess
import time

import cv2
import numpy as np
from libcamera import controls
from picamera2 import MappedArray, Picamera2, Preview
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

import config

# One status bar per stream: (stream, frame height, bar height, font scale, thickness, padding)
BARS = [("main", config.HEIGHT, 36, 0.8, 2, 10)]
if config.PREVIEW:
    BARS.append(("lores", config.SCREEN_HEIGHT, 24, 0.5, 1, 6))


def find_usb_mic():
    """Return the ALSA name of the first USB mic, e.g. 'plughw:2,0', or None."""
    out = subprocess.run(["arecord", "-l"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("card") and "USB" in line:
            card = line.split()[1].rstrip(":")
            device = line.split("device ")[1].split(":")[0]
            return f"plughw:{card},{device}"
    return None


class Recorder:
    def __init__(self, folder, gps=None):
        self.folder = folder
        self.gps = gps
        self.camera = None
        self.ffmpeg_process = None
        self.mic = None
        self.bars = {}
        self.bar_second = None

    def start(self):
        if self.camera:
            return
        self.mic = find_usb_mic()

        # ffmpeg muxes the camera's H.264 (from stdin) with the mic and cuts 1-minute clips
        audio_in = ["-f", "alsa", "-ac", "1", "-ar", str(config.AUDIO_RATE),
                    "-thread_queue_size", "1024", "-i", self.mic] if self.mic else []
        audio_out = ["-c:a", "aac", "-b:a", config.AUDIO_BITRATE] if self.mic else []
        self.ffmpeg_process = subprocess.Popen([
            "ffmpeg", "-loglevel", "error", *audio_in,
            "-use_wallclock_as_timestamps", "1", "-thread_queue_size", "64",
            "-f", "h264", "-i", "-", "-c:v", "copy", *audio_out,
            "-f", "segment", "-segment_time", str(config.CLIP_SECONDS),
            "-reset_timestamps", "1", "-strftime", "1",
            "-segment_format_options", "movflags=+frag_keyframe+empty_moov",
            f"{self.folder}/%Y-%m-%d_%H-%M-%S.mp4",
        ], stdin=subprocess.PIPE)

        # YUV420 is what the hardware encoder takes natively and is less than half the size of RGB
        streams = {"main": {"size": (config.WIDTH, config.HEIGHT), "format": "YUV420"}}
        if config.PREVIEW:
            streams["lores"] = {"size": (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), "format": "YUV420"}

        self.camera = Picamera2()
        self.camera.configure(self.camera.create_video_configuration(
            **streams,
            display="lores" if config.PREVIEW else None,
            buffer_count=config.BUFFER_COUNT,
            controls={"FrameRate": config.FRAMERATE,
                      "AfMode": controls.AfModeEnum.Manual,
                      "LensPosition": config.LENS_POSITION},
        ))
        if config.STATUS_BAR:
            self.camera.pre_callback = self.draw_status_bar
        if config.PREVIEW:
            self.camera.start_preview(Preview.DRM, x=config.PREVIEW_X, y=config.PREVIEW_Y,
                                      width=config.SCREEN_WIDTH, height=config.SCREEN_HEIGHT)
        encoder = H264Encoder(bitrate=config.BITRATE, repeat=True,
                              iperiod=config.FRAMERATE * config.KEYFRAME_SECONDS)
        self.camera.start_recording(encoder, FileOutput(self.ffmpeg_process.stdin))

    def draw_status_bar(self, request):
        now = int(time.time())
        new_second = now != self.bar_second
        self.bar_second = now
        if new_second:      # only build the text once a second, not on every frame
            text = time.strftime("REC %Y-%m-%d %H:%M:%S ", time.localtime(now)) + \
                ("MIC ON" if self.mic else "MIC OFF")
            if self.gps:
                text += "  " + self.gps.status_text()

        for stream, frame_h, bar_h, scale, thickness, pad in BARS:
            with MappedArray(request, stream) as m:
                if new_second:
                    # Draw on the Y (brightness) plane only: 0 = black bar, 255 = white text
                    bar = np.zeros((bar_h, m.array.shape[1]), np.uint8)
                    cv2.putText(bar, text, (pad, bar_h - pad), cv2.FONT_HERSHEY_SIMPLEX,
                                scale, 255, thickness)
                    self.bars[stream] = bar
                m.array[frame_h - bar_h:frame_h] = self.bars[stream]

    def stop(self):
        if not self.camera:
            return
        self.camera.stop_recording()
        self.camera.close()
        self.camera = None
        self.ffmpeg_process.stdin.close()
        try:
            self.ffmpeg_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.ffmpeg_process.terminate()
            self.ffmpeg_process.wait()
        self.ffmpeg_process = None