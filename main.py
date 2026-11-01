import config
import storage
from recorder import Recorder
from pathlib import Path
import signal
import time

def main():
    folder = Path(config.RECORDING_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    rec = Recorder(folder)
    try:
        rec.start()
        while rec.ffmpeg_process.poll() is None:
            storage.delete_old_clips(folder)
            time.sleep(10)
        print(f"ffmpeg exited with code {rec.ffmpeg_process.returncode}")
    except KeyboardInterrupt:
        pass
    finally: rec.stop()

if __name__ == "__main__":
    main()


