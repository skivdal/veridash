import os
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


    def get_video_download_url(self, object_name: str) -> str | None:
        return self._client.get_presigned_url("GET", "veridash", object_name)


    def file_exists(self, object_name: str) -> bool:
        return len(list(self._client.list_objects("veridash", prefix=object_name))) == 1


    def download_file(self, object_name: str, local_filename: str | None = None) -> str:
        """
        Download object, short circuit if already in filesystem
        :param object_name: Name of the file in the veridash bucket
        :param local_filename: Optional local location to put/check for the file. Defaults to /tmp/[object_name]
        :returns: Local file path
        """
        if not local_filename:
            local_filename = f"/tmp/{object_name}"

        if not os.path.exists(local_filename):
            self._client.fget_object("veridash", object_name, local_filename)

        return local_filename


if __name__ == "__main__":
    mgr = StorageManager()

