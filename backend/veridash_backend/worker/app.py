import gc
import torch
import ffmpeg
import whisper
from celery import Celery
from veridash_backend.worker.translation import Translator
from veridash_backend.commons.storage import StorageManager
from veridash_backend.commons.mutex import LockManager
from veridash_backend.commons.db import Database


app = Celery("worker", broker="redis://localhost:6379/0", backend="redis://localhost:6379/0",
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
    with locks.wait_for_lock("gpu", expiration=180):
        model = whisper.load_model("medium")
        res = model.transcribe(local_name)

        del model
        gc.collect();
        if torch.cuda.device_count() != 0:
            torch.cuda.empty_cache()

    res["segments"] = [x for x in res["segments"] if x["no_speech_prob"] < 0.7]
    for x in res["segments"]:
        x.pop("tokens")

    if res["language"] != "en" and res["text"].strip():
        t = Translator()
        translations = t.translate_sentences([x["text"] for x in res["segments"]])

        for x, y in zip(res["segments"], translations):
            x["text_en"] = y

    return {
        "transcription": res,
    }

