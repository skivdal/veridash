import json
import hashlib
from os import path
from uuid import uuid4
from psycopg_pool import NullConnectionPool
from veridash_backend.commons.settings import Settings

class Database:
    def __init__(self):
        settings = Settings()

        self.pool = NullConnectionPool(settings.POSTGRES_CONN_STR)
        self.pool.open()


    def provision_object_name(self, user_id: int, filename: str, file_hash: str | None) -> str:
        _, ext = path.splitext(filename)
        obj_name = str(uuid4()) + ext

        with self.pool.connection() as conn:
            conn.execute("INSERT INTO videos (owner_id, filename, hash_sha256, object_name) VALUES (%s, %s, %s, %s);",
                         (user_id, filename, file_hash, obj_name))

        return obj_name


    def video_belongs_to_user(self, user_id: int, object_name: str) -> bool:
        with self.pool.connection() as conn:
            res = conn.execute("SELECT id FROM videos WHERE owner_id = %s AND object_name = %s;",
                               (user_id, object_name)).fetchone()

        return res is not None


    def add_video_hash_if_not_exists(self, object_name: str, local_path: str):
        with self.pool.connection() as conn:
            res = conn.execute("SELECT hash_sha256 FROM videos WHERE object_name = %s;", (object_name, )).fetchone()
            if res is not None and res[0] != None:
                return

        hasher = hashlib.sha256()
        with open(local_path, 'rb') as f:
            while True:
                # reading at 1MB chunks
                data = f.read(1_000_000)
                if not data:
                    break

                hasher.update(data)

        digest = hasher.hexdigest()
        with self.pool.connection() as conn:
            conn.execute("UPDATE videos SET hash_sha256 = %s WHERE object_name = %s;", (digest, object_name))


    def add_video_keyframes(self, video_name: str, image_names: list[str]) -> list[str]:
        with self.pool.connection() as conn:
            video_id = conn.execute("SELECT id FROM videos WHERE object_name = %s;", (video_name, )).fetchone()
            if video_id is None:
                return []
            video_id = video_id[0]

        insert_tuples = []
        frame_count = len(image_names)
        for i, name in enumerate(image_names):
            _, ext = path.splitext(name)
            obj_name = str(uuid4()) + ext

            insert_tuples.append((video_id, obj_name, i+1, frame_count))

        with self.pool.connection() as conn:
            conn.cursor().executemany("""
                INSERT INTO images (video_id, object_name, frame_number, total_frames)
                VALUES (%s, %s, %s, %s);
            """, insert_tuples)

        return [x[1] for x in insert_tuples]
    
    
    def add_detected_objects(self, video_name: str, image_names: list[str]) -> list[str]:
        with self.pool.connection() as conn:
            video_id = conn.execute("SELECT id FROM videos WHERE object_name = %s;", (video_name, )).fetchone()
            if video_id is None:
                return []
            video_id = video_id[0]

        insert_tuples = []
        frame_count = len(image_names)
        for i, name in enumerate(image_names):
            _, ext = path.splitext(name)
            obj_name = str(uuid4()) + ext

            insert_tuples.append((video_id, obj_name, i+1, frame_count))

        with self.pool.connection() as conn:
            conn.cursor().executemany("""
                INSERT INTO detected_objects (video_id, object_name, frame_number, total_frames)
                VALUES (%s, %s, %s, %s);
            """, insert_tuples)

        return [x[1] for x in insert_tuples]


    def get_cached_results(self, object_name: str, job_type: str) -> dict | None:
        with self.pool.connection() as conn:
            res = conn.execute("""
                SELECT r.job_result FROM job_results r
                INNER JOIN videos v ON v.id = r.video_id
                WHERE r.job_type = %s
                AND v.hash_sha256 = (SELECT hash_sha256 FROM videos
                                     WHERE object_name = %s AND hash_sha256 is not null
                                     LIMIT 1)
                ORDER BY r.id DESC
                LIMIT 1;
                """, (job_type, object_name)).fetchone()

        if res is None:
            return None

        return res[0]


    def store_job_result(self, object_name: str, job_type: str, job_result: dict):
        with self.pool.connection() as conn:
            conn.execute("""
                INSERT INTO job_results (video_id, job_type, job_result)
                VALUES (
                    (SELECT id FROM videos WHERE object_name = %s),
                    %s, %s
                );
            """, (object_name, job_type, json.dumps(job_result)))


    def get_images_by_video_id(self, video_name: str) -> list[str]:
        with self.pool.connection() as conn:
            video_id = conn.execute("SELECT id FROM videos WHERE object_name = %s;", (video_name, )).fetchone()
            video_id = video_id[0]
            print(video_id, flush=True)
            res = conn.execute("SELECT object_name FROM images WHERE video_id = %s ORDER BY frame_number ASC;", (video_id,)).fetchall()

        image_names = [row[0] for row in res]
        return image_names

if __name__ == "__main__":
    db = Database()

