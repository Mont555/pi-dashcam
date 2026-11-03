import subprocess
import time

MAIN_BAR = 36    # status bar height on the recording, in pixels
LORES_BAR = 24   # status bar height on the screen preview
    
def mic_plugged_in():
    output = subprocess.run(["arecord", "-l"], capture_output=True, text=True).stdout
    return "USB" in output 

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
        if config.STATUS_BAR:
            import cv2
            import numpy as np
            self._cv2, self._np, self._MappedArray = cv2, np, MappedArray
 
        self.mic = config.MIC_DEVICE if mic_plugged_in() else None
        self.ffmpeg_process = subprocess.Popen(self.ffmpeg_command(), stdin=subprocess.PIPE)
        self.camera = Picamera2()
 
        # YUV420 is what the hardware encoder takes natively, and is under half
        # the size of the default XBGR8888 (3 MB vs 8 MB per 1080p frame). On a
        # Pi 3 memory bandwidth is the bottleneck, so this is the biggest win.
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