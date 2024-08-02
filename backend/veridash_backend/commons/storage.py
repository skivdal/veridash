from minio import Minio


class StorageManager:
    def __init__(self):
        self._client = Minio("localhost:9000",
            access_key="veridash",
            secret_key="njW2uWLiV8FLUJ6kYpsF",
            secure=False,
        )

        assert self._client.bucket_exists("veridash"), "veridash bucket does not exist"


    def get_video_upload_url(self, object_name: str) -> str | None:
        return self._client.get_presigned_url("PUT", "veridash", object_name)


    def file_exists(self, object_name: str) -> bool:
        return len(list(self._client.list_objects("veridash", prefix=object_name))) == 1


if __name__ == "__main__":
    mgr = StorageManager()

