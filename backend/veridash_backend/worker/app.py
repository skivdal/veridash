import gc
import torch
import ffmpeg
import whisper
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


@app.task(bind=True)
def get_transcription(self, video_name: str):
    local_name = grab_video_locally(video_name)

    # to prevent OOM-errors, we wait for gpu
    with locks.wait_for_lock("gpu", expiration=100):
        model = whisper.load_model("medium")
        res = model.transcribe(local_name)

        gc.collect();
        if torch.cuda.device_count() != 0:
            torch.cuda.empty_cache();
        del model

        res_en = None
        # if we need translation
        if res["language"] != "en" and res["text"].strip():
            model = whisper.load_model("medium.en")
            res_en = model.transcribe(local_name)

            gc.collect();
            if torch.cuda.device_count() != 0:
                torch.cuda.empty_cache();
            del model

    for x in res["segments"]:
        x.pop("tokens")

    if res_en:
        for x in res_en["segments"]:
            x.pop("tokens")

    return {
        "transcription": res,
        "translation": res_en,
    }

