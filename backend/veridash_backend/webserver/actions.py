from veridash_backend.commons.db import Database
from veridash_backend.commons.storage import StorageManager


db = Database()
storage = StorageManager()


class Handler:
    @classmethod
    def handle_message(cls, user_id: int, data: dict) -> dict | None:
        if "messageType" not in data:
            raise KeyError("Expected messageType in data")

        match data["messageType"]:
            case "source":
                obj_name = db.provision_object_name(user_id, data["filename"])
                url = storage.get_video_upload_url(obj_name)

                return {
                    "messageType": data["messageType"],
                    "videoId": obj_name,
                    "uploadUrl": url,
                }

        return None

