import ffmpeg
from celery import Celery
from veridash_backend.commons.storage import StorageManager
from veridash_backend.commons.mutex import LockManager
from veridash_backend.commons.db import Database


app = Celery('worker', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0',
             broker_connection_retry_on_startup=True)
storage = StorageManager()
locks = LockManager()
db = Database()


def grab_video_locally(video_name: str):
    # somewhat arbitrary 10 minute expected max download time
    with locks.wait_for_lock(f"download:{video_name}", expiration=600):
        local_name = storage.download_file(video_name)

    db.add_video_hash_if_not_exists(video_name, local_name)
    return local_name


@app.task(bind=True)
def get_metadata(self, video_name: str):
    local_name = grab_video_locally(video_name)
    return ffmpeg.probe(local_name)

