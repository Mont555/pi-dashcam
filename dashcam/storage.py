import shutil
from pathlib import Path

def free_bytes(folder):
    return shutil.disk_usage(folder).free