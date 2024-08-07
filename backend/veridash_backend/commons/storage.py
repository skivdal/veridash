import os
from minio import Minio
from veridash_backend.commons.settings import Settings


class StorageManager:
    def __init__(self):
        self.settings = Settings()

        self._client = Minio(self.settings.MINIO_HOST,
            access_key=self.settings.MINIO_USER,
            secret_key=self.settings.MINIO_PASS,
            secure=self.settings.MINIO_SECURE,
        )

        assert self._client.bucket_exists(self.settings.MINIO_BUCKET), \
            f"{self.settings.MINIO_BUCKET} bucket does not exist"


    def get_video_upload_url(self, object_name: str) -> str | None:
        return self._client.get_presigned_url("PUT", self.settings.MINIO_BUCKET, object_name)


    def get_video_download_url(self, object_name: str) -> str | None:
        return self._client.get_presigned_url("GET", self.settings.MINIO_BUCKET, object_name)


    def file_exists(self, object_name: str) -> bool:
        return len(list(self._client.list_objects(self.settings.MINIO_BUCKET, prefix=object_name))) == 1


    def download_file(self, object_name: str, local_filename: str | None = None) -> str:
        """
        Download object, short circuit if already in filesystem
        :param object_name: Name of the file in the veridash bucket
        :param local_filename: Optional local location to put/check for the file. Defaults to /tmp/[object_name]
        :returns: Local file path
        """
        if not local_filename:
            local_filename = f"{self.settings.TEMP_STORAGE_DIR}/{object_name}"

        if not os.path.exists(local_filename):
            self._client.fget_object(self.settings.MINIO_BUCKET, object_name, local_filename)

        return local_filename


    def upload_file(self, object_name: str, local_filename: str):
        self._client.fput_object(self.settings.MINIO_BUCKET, object_name, local_filename)


if __name__ == "__main__":
    mgr = StorageManager()

