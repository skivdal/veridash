from werkzeug.utils import secure_filename
from veridash_backend.commons.db import Database
from veridash_backend.commons.storage import StorageManager
from veridash_backend.worker.app import get_metadata, get_transcription


db = Database()
storage = StorageManager()


class Handler:
    @classmethod
    def handle_message(cls, user_id: int, data: dict) -> dict | tuple | None:
        if "messageType" not in data:
            raise KeyError("Expected messageType in data")

        if "videoId" not in data and data["messageType"] != "source":
            raise KeyError("Expected videoId in data")

        # handle non-cacheable messages
        match data["messageType"]:
            case "source":
                file_name, file_hash = data["filename"].rsplit(':', maxsplit=1)
                file_name = secure_filename(file_name)
                if len(file_hash) != 64:
                    file_hash = None

                obj_name = db.provision_object_name(user_id, file_name, file_hash)
                upload_url = storage.get_video_upload_url(obj_name)
                download_url = storage.get_video_download_url(obj_name)

                return {
                    "messageType": data["messageType"],
                    "videoId": obj_name,
                    "uploadUrl": upload_url,
                    "downloadUrl": download_url,
                }

        # if the video does not belong to the user, or is not uploaded, something is wrong
        if not db.video_belongs_to_user(user_id, data["videoId"]) or not storage.file_exists(data["videoId"]):
            raise ValueError("The provided videoId does not belong to an uploaded video")

        # Return cached results if exists
        cached_result = db.get_cached_results(data["videoId"], data["messageType"])
        if cached_result:
            return {
                "messageType": data["messageType"],
                "videoId": data["videoId"],
                **cached_result,
            }

        # might be cached
        match data["messageType"]:
            case "metadata":
                task_id: str = get_metadata.apply_async((data["videoId"], )).id  # ignore the error on this line
            case "transcription":
                task_id: str = get_transcription.apply_async((data["videoId"], )).id  # ignore the error on this line
            case _:
                raise NotImplementedError(f"The messageType {data['messageType']} is not yet implemented")

        return (task_id, data["messageType"], data["videoId"])

