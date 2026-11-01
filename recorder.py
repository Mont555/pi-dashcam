import config
import subprocess

class Recorder:
    def __init__(self, folder):
        self.folder = folder
        self.camera = None
        self.ffmpeg_process = None
        
    def ffmpeg_command(self):
        return ["ffmpeg", "-loglevel", "error",
        # Sound from the USB microphone
        "-f", "alsa", "-ac", "1", "-ar", "48000", "-thread_queue_size", "1024", "-i", config.MIC_DEVICE,
        # Video from the camera (pipe)
        "-use_wallclock_as_timestamps", "1", "-thread_queue_size", "64", "-f", "h264", "-i", "-",
        # Processing & Compression
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "96k",
        # Segmenting and Crash-Proofing
        "-f", "segment", "-segment_time", str(config.CLIP_SECONDS),
        "-reset_timestamps", "1", "-strftime", "1",
        "-segment_format_options", "movflags=+frag_keyframe+empty_moov",
        f"{self.folder}/%Y-%m-%d_%H-%M-%S.mp4"
        ]

    def start(self):
        from picamera2 import Picamera2, Preview
        from picamera2.encoders import H264Encoder
        from picamera2.outputs import FileOutput
        from libcamera import controls
        if self.camera:
            return
        self.ffmpeg_process = subprocess.Popen(self.ffmpeg_command(), stdin=subprocess.PIPE)
        self.camera = Picamera2()
        self.camera.configure(self.camera.create_video_configuration(
            main={"size": (config.WIDTH, config.HEIGHT)},
            lores={"size": (config.PREVIEW_WIDTH, config.PREVIEW_HEIGHT)},
            display="lores",
            controls={"FrameRate": config.FRAMERATE,
                      "AfMode": controls.AfModeEnum.Manual,
                      "LensPosition": 0.0,},
        ))
        self.camera.start_preview(Preview.DRM)
        encoder = H264Encoder(bitrate=config.BITRATE, repeat=True, iperiod=config.FRAMERATE)
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