from veridash_backend.commons.db import Database
from veridash_backend.commons.storage import StorageManager
from veridash_backend.worker.app import long_task


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
                obj_name = db.provision_object_name(user_id, data["filename"])
                url = storage.get_video_upload_url(obj_name)

                return {
                    "messageType": data["messageType"],
                    "videoId": obj_name,
                    "uploadUrl": url,
                }

        # if the video does not belong to the user, or is not uploaded, something is wrong
        if not db.video_belongs_to_user(user_id, data["videoId"]) or not storage.file_exists(data["videoId"]):
            raise ValueError("The provided videoId does not belong to an uploaded video")

        # Return cached results if exists
        # TODO: test
        cached_result = db.get_cached_results(data["videoId"], data["messageType"])
        if cached_result:
            print(cached_result)
            return {
                "messageType": data["messageType"],
                "videoId": data["videoId"],
                **cached_result,
            }

        # might be cached
        match data["messageType"]:
            case "metadata":
                task_id: str = long_task.apply_async((10, 3)).id  # ignore the error on this line
            case _:
                raise NotImplementedError(f"The messageType {data['messageType']} is not yet implemented")

        return (task_id, data["messageType"], data["videoId"])

