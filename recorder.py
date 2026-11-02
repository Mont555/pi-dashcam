import config
import subprocess
import time

MAIN_BAR = 36    # status bar height on the recording, in pixels
LORES_BAR = 24   # status bar height on the screen preview
    
def mic_plugged_in():
    output = subprocess.run(["arecord", "-l"], capture_output=True, text=True).stdout
    return "USB" in output 

class Recorder:
    def __init__(self, folder):
        self.folder = folder
        self.camera = None
        self.mic = None
        self.ffmpeg_process = None
        # Status bar cache: redrawn once a second, copied into every frame
        self._last_sec = None
        self._main_bar = None
        self._lores_bar = None
 
    def ffmpeg_command(self):
        start = ["ffmpeg", "-loglevel", "error"]
        # Sound from the USB microphone
        audio_in = ["-f", "alsa", "-ac", "1", "-ar", str(config.AUDIO_RATE),
                    "-thread_queue_size", "1024", "-i", self.mic]
        # Video from the camera (pipe), already H.264 from the hardware encoder
        video_in = ["-use_wallclock_as_timestamps", "1", "-thread_queue_size", "64",
                    "-f", "h264", "-i", "-", "-c:v", "copy"]
        # Processing & Compression
        audio_out = ["-c:a", "aac", "-b:a", config.AUDIO_BITRATE]
        # Segmenting and Crash-Proofing
        save = ["-f", "segment", "-segment_time", str(config.CLIP_SECONDS),
                "-reset_timestamps", "1", "-strftime", "1",
                "-segment_format_options", "movflags=+frag_keyframe+empty_moov",
                f"{self.folder}/%Y-%m-%d_%H-%M-%S.mp4"]
        if self.mic:
            return start + audio_in + video_in + audio_out + save
        return start + video_in + save
 
    def _render_bars(self, now, main_stride, lores_stride):
        # Both streams are YUV420, so we draw onto the luma (Y) plane only:
        # 0 = black bar, 255 = white text. One small render per second.
        cv2 = self._cv2
        np = self._np
        mic = "MIC ON" if self.mic else "MIC OFF"
        text = time.strftime(f"REC %Y-%m-%d %H:%M:%S {mic}", time.localtime(now))
 
        bar = np.zeros((MAIN_BAR, main_stride), np.uint8)
        cv2.putText(bar, text, (10, MAIN_BAR - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 255, 2)
        self._main_bar = bar
 
        bar = np.zeros((LORES_BAR, lores_stride), np.uint8)
        cv2.putText(bar, text, (6, LORES_BAR - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 1)
        self._lores_bar = bar
 
    def draw_status_bar(self, request):
        MappedArray = self._MappedArray
        now = int(time.time())
        with MappedArray(request, "main") as main:
            if config.PREVIEW:
                with MappedArray(request, "lores") as lores:
                    if now != self._last_sec:
                        self._last_sec = now
                        self._render_bars(now, main.array.shape[1], lores.array.shape[1])
                    h = config.SCREEN_HEIGHT
                    lores.array[h - LORES_BAR:h] = self._lores_bar
            elif now != self._last_sec:
                self._last_sec = now
                self._render_bars(now, main.array.shape[1], 1)
            # In YUV420 the array is (1.5 * height) rows tall: Y plane first, then chroma.
            h = config.HEIGHT
            main.array[h - MAIN_BAR:h] = self._main_bar
 
    def start(self):
        from picamera2 import Picamera2, Preview, MappedArray
        from picamera2.encoders import H264Encoder
        from picamera2.outputs import FileOutput
        from libcamera import controls
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
            streams["lores"] = {"size": (config.SCREEN_WIDTH, config.SCREEN_HEIGHT),
                                "format": "YUV420"}
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