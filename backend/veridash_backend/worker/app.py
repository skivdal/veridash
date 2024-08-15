import os
import gc
import torch
import ffmpeg
import whisper
from celery import Celery
from veridash_backend.worker.translation import Translator
from veridash_backend.commons.storage import StorageManager
from veridash_backend.commons.mutex import LockManager
from veridash_backend.commons.db import Database
from veridash_backend.commons.settings import Settings


settings = Settings()

app = Celery("worker", broker=settings.REDIS_CONN_STR, backend=settings.REDIS_CONN_STR,
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

    if res["language"] != "en" and type(res["text"]) == str and res["text"].strip():
        try:
            t = Translator()
            translations = t.translate_sentences([x["text"] for x in res["segments"]])

            for x, y in zip(res["segments"], translations):
                x["text_en"] = y
        except EnvironmentError:
            pass

    return {
        "transcription": res,
    }


@app.task(bind=True)
def get_coordinates(self, video_name: str):
    # TODO: use transcript named entity recognition and geocoding
    # TODO: use osm tags

    local_name = grab_video_locally(video_name)
    metadata = ffmpeg.probe(local_name)

    has_tags = ("format" in metadata and type(metadata["format"]) == dict and
                "tags" in metadata["format"] and type(metadata["format"]["tags"]) == dict)

    if not has_tags:
        return {
            "latlng": None,
        }

    # TODO: this should be extended to cover as many formats as possible.
    # We could also go by other methods if not present in metadata (approx. from transcript, OSM tags, etc.)
    if "location" in metadata["format"]["tags"]:
        l = metadata["format"]["tags"]["location"]
    elif "com.apple.quicktime.location.ISO6709" in metadata["format"]["tags"]:
        l = metadata["format"]["tags"]["com.apple.quicktime.location.ISO6709"]
    else:
        return {
            "latlng": None,
        }

    try:
        lat, lng = map(lambda x: float(''.join([n for n in x if n.isdigit() or n == '.'])), l.split('+')[1:3])
        coords = [lat, lng]
    except:
        coords = None

    return {
        "latlng": coords
    }


@app.task(bind=True)
def get_keyframes(self, video_name: str):
    local_name = grab_video_locally(video_name)

    out_folder = os.path.join(settings.TEMP_STORAGE_DIR, f"{video_name}-frames")
    os.makedirs(out_folder, exist_ok=True)

    # sample 1 frame per second
    ffmpeg \
        .input(local_name) \
        .filter('fps', fps=1) \
        .output(os.path.join(out_folder, "frame_%04d.jpg"), format='image2', vcodec='mjpeg') \
        .run()

    images = os.listdir(out_folder)

    img_obj_names = db.add_video_keyframes(video_name, images)

    download_urls = []
    for obj, local in zip(img_obj_names, images):
        local_path = os.path.join(out_folder, local)

        storage.upload_file(obj, local_path)
        download_urls.append(storage.get_video_download_url(obj))

        os.remove(local_path)

    os.rmdir(out_folder)

    return {
        "urls": download_urls,
    }

