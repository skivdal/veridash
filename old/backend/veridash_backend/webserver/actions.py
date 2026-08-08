from werkzeug.utils import secure_filename
from veridash_backend.commons.db import Database
from veridash_backend.commons.storage import StorageManager
from veridash_backend.worker.app import get_metadata, get_transcription, get_coordinates, get_keyframes, get_objects, \
    get_stitch


db = Database()
storage = StorageManager()


class Handler:
    @classmethod
    def handle_message(cls, user_id: int, data: dict) -> dict | tuple | None:
        if "messageType" not in data:
            raise KeyError("Expected messageType in data")

        if "videoId" not in data and data["messageType"] != "source":
            raise KeyError("Expected videoId in data")

        if "sourceKeyFrames" not in data and data["messageType"] == "stitching":
            raise KeyError("Expected sourceKeyFrames in data")

        # handle source message
        if data["messageType"] == "source":
            file_name, file_hash = data["filename"].rsplit(':', maxsplit=1)
            file_name = secure_filename(file_name)
            if len(file_hash) != 64:
                file_hash = None

            obj_name = db.provision_object_name(user_id, file_name, file_hash)
            upload_url = storage.get_object_upload_url(obj_name)
            download_url = storage.get_object_download_url(obj_name)

            return {
                "messageType": data["messageType"],
                "videoId": obj_name,
                "uploadUrl": upload_url,
                "downloadUrl": download_url,
            }

        # if the video does not belong to the user, or is not uploaded, something is wrong
        if not db.video_belongs_to_user(user_id, data["videoId"]) or not storage.file_exists(data["videoId"]):
            raise ValueError("The provided videoId does not belong to an uploaded video")

        # handle non-cacheable messages
        match data["messageType"]:
            case "keyframes":  # TODO: add: , "objectdetection":
                if data["messageType"] == "keyframes":
                    img_names = db.get_images_by_video_name(data["videoId"])
                else:
                    img_names = db.get_detections_by_video_name(data["videoId"])

                presigned_urls = []
                for n in img_names:
                    u = storage.get_object_download_url(n)
                    if u is None:
                        continue

                    presigned_urls.append(u)

                if len(presigned_urls) != 0:
                    return {
                        "messageType": data["messageType"],
                        "videoId": data["videoId"],
                        "urls": presigned_urls,
                    }
            case "stitching":
                # NOTE: might be cached, would require lookup based on identical source frames
                # computing it every time for now...
                task_id: str = get_stitch.apply_async((data["videoId"], data["sourceKeyFrames"])).id # ignore the error on this line

 
        # Return cached results if exists
        cached_result = db.get_cached_results(data["videoId"], data["messageType"])
        # NOTE: object detection too unstable at the moment
        if cached_result and data["messageType"] not in ("objectdetection", "stitching"):
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
            case "map":
                task_id: str = get_coordinates.apply_async((data["videoId"], )).id # ignore the error on this line
            case "keyframes":  # NOTE: this should never be served from cache
                task_id: str = get_keyframes.apply_async((data["videoId"], )).id # ignore the error on this line
            case "objectdetection":  # NOTE: this should never be served from cache
                task_id: str = get_objects.apply_async((data["videoId"], )).id # ignore the error on this line
            case "stitching":
                pass
            case _:
                raise NotImplementedError(f"The messageType {data['messageType']} is not yet implemented")

        return (task_id, data["messageType"], data["videoId"])

