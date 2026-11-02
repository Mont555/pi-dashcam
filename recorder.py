import config
import subprocess
import time
    
def mic_plugged_in():
    output = subprocess.run(["arecord", "-l"], capture_output=True, text=True).stdout
    return "USB" in output 

class Recorder:
    def __init__(self, folder):
        self.folder = folder
        self.camera = None
        self.mic = None
        self.ffmpeg_process = None
        self.status_second = None
        self.status_text = ""
        
    def ffmpeg_command(self):
        start = ["ffmpeg", "-loglevel", "error"]
        # Sound from the USB microphone
        audio_in = ["-f", "alsa", "-ac", "1", "-ar", "48000", "-thread_queue_size", "1024", "-i", self.mic]
        # Video from the camera (pipe)
        video_in = ["-use_wallclock_as_timestamps", "1", "-thread_queue_size", "64", "-f", "h264", "-i", "-", "-c:v", "copy",]
        # Processing & Compression
        audio_out = ["-c:a", "aac", "-b:a", "96k"]
        # Segmenting and Crash-Proofing
        save = ["-f", "segment", "-segment_time", str(config.CLIP_SECONDS),
        "-reset_timestamps", "1", "-strftime", "1",
        "-segment_format_options", "movflags=+frag_keyframe+empty_moov",
        f"{self.folder}/%Y-%m-%d_%H-%M-%S.mp4"]
        if self.mic:
            return start + audio_in + video_in + audio_out + save
        else:
            return start + video_in + save

    def draw_status_bar(self, request):
        import cv2
        from picamera2 import MappedArray

        now = int(time.time())
        if now != self.status_second:
            self.status_second = now
            clock = time.strftime("%Y-%m-%d  %H:%M:%S", time.localtime(now))
            mic = "MIC ON" if self.mic_on else "MIC OFF"
            self.status_text = f"REC {clock} {mic}"
        with MappedArray(request, "main") as m:
            frame = m.array
            frame_height, frame_width = frame.shape[:2]
            bar_height = config.STATUS_BAR_HEIGHT
            y_position = frame_height - bar_height
            cv2.rectangle(frame, (0, y_position), (frame_width,  y_position + bar_height), (0, 0, 0, 255), -1)
            text_y = y_position + int(bar_height * 0.72)
            cv2.putText(frame, self.status_text, (10, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, config.STATUS_BAR_FONT_SCALE,
                        (255, 255, 255, 255), 2, cv2.LINE_AA)

    def start(self):
        from picamera2 import Picamera2, Preview
        from picamera2.encoders import H264Encoder
        from picamera2.outputs import FileOutput
        from libcamera import controls
        if self.camera:
            return
        self.mic = mic_plugged_in()
        self.ffmpeg_process = subprocess.Popen(self.ffmpeg_command(), stdin=subprocess.PIPE)
        self.camera = Picamera2()
        self.camera.configure(self.camera.create_video_configuration(
            main={"size": (config.WIDTH, config.HEIGHT)},
            display="main",
            controls={"FrameRate": config.FRAMERATE,
                      "AfMode": controls.AfModeEnum.Manual,
                      "LensPosition": 0.0,},
        ))
        if config.STATUS_BAR:
            self.camera.pre_callback = self.draw_status_bar
        if config.PREVIEW:
            self.camera.start_preview(Preview.DRM, x=config.PREVIEW_X, y=config.PREVIEW_Y, width=config.SCREEN_WIDTH, height=config.SCREEN_HEIGHT)
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