from pathlib import Path
from dashcam import config
from dashcam import storage 

def make_files(folder, *names):
    for date in names:
        (folder / date).write_text("pretend video")

def test_delete_old_clips(tmp_path, monkeypatch):
       make_files(tmp_path, "2026-01-01_09-00-00.mp4", "2026-01-01_09-01-00.mp4", "2026-01-01_09-02-00.mp4")

       def fake_free_bytes(folder):
            if len(list(folder.iterdir())) > 2:
                 return 1000000000  
            return 5000000000
       monkeypatch.setattr(storage, "free_bytes", fake_free_bytes)
       storage.delete_old_clips(tmp_path) 
       assert not (tmp_path / "2026-01-01_09-00-00.mp4").exists() # Deleted Recording
       assert (tmp_path / "2026-01-01_09-01-00.mp4").exists()
       assert (tmp_path / "2026-01-01_09-02-00.mp4").exists()

def test_nothing_deleted(tmp_path, monkeypatch):
         make_files(tmp_path, "2026-01-01_09-00-00.mp4", "2026-01-01_09-01-00.mp4", "2026-01-01_09-02-00.mp4")
         monkeypatch.setattr(storage, "free_bytes", lambda free: 5000000000)
         storage.delete_old_clips(tmp_path)
         assert (tmp_path / "2026-01-01_09-00-00.mp4").exists()
         assert (tmp_path / "2026-01-01_09-01-00.mp4").exists()
         assert (tmp_path / "2026-01-01_09-02-00.mp4").exists()


def test_never_deletes_file_being_recorded(tmp_path, monkeypatch):
         make_files(tmp_path, "2026-01-01_09-00-00.mp4", "2026-01-01_09-01-00.mp4", "2026-01-01_09-02-00.mp4")
         monkeypatch.setattr(storage, "free_bytes", lambda free: 1000000000)
         storage.delete_old_clips(tmp_path)
         assert not (tmp_path / "2026-01-01_09-00-00.mp4").exists()
         assert not (tmp_path / "2026-01-01_09-01-00.mp4").exists()
         assert (tmp_path / "2026-01-01_09-02-00.mp4").exists() # Active Recording