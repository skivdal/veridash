from minio import Minio


class StorageManager:
    def __init__(self):
        self._client = Minio("localhost:9000",
            access_key="veridash",
            secret_key="njW2uWLiV8FLUJ6kYpsF",
            secure=False,
        )

        assert self._client.bucket_exists("veridash"), "veridash bucket does not exist"


    def get_video_upload_url(self, filename: str) -> str | None:
        return self._client.get_presigned_url("POST", "veridash", filename)


if __name__ == "__main__":
    mgr = StorageManager()

