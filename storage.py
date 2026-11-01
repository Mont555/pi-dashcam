import shutil
from pathlib import Path
import config

def free_bytes(folder):
    return shutil.disk_usage(folder).free

def delete_old_clips(folder):
    while free_bytes(folder) < config.MIN_FREE_BYTES:
        files = sorted(Path(folder).iterdir())
        if len(files) <= 1:
            break
        files[0].unlink()