# Video Settings
WIDTH = 1920
HEIGHT = 1080
FRAMERATE = 25                # 30 -> 25 is ~17% less work for the ISP, encoder and SD card
BITRATE = 7_000_000           # 10 Mbps is more than dashcam footage needs
KEYFRAME_SECONDS = 2          # longer GOP = same quality at lower bitrate; clips split on these
BUFFER_COUNT = 4              # Pi 3 has little CMA memory; 4 is enough for recording
LENS_POSITION = 0.4
CLIP_SECONDS = 60
 
# Storage Settings
RECORDING_DIR = "/home/pi/recordings"
MIN_FREE_BYTES = 2000000000
STORAGE_CHECK_SECONDS = 30
 
# GPS Settings
GPS_PORT = "/dev/ttyACM0"
GPS_BAUD = 9600
 
# Microphone Settings
MIC_DEVICE = "plughw:2,0"
AUDIO_RATE = 24000            # plenty for voice; less CPU for the software AAC encoder
AUDIO_BITRATE = "48k"
 
# Preview Settings
PREVIEW = True
STATUS_BAR = True
PREVIEW_X = 0
PREVIEW_Y = 15
SCREEN_WIDTH = 800    
SCREEN_HEIGHT = 450