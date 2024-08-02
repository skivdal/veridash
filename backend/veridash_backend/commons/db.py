from os import path
from uuid import uuid4
from psycopg_pool import ConnectionPool


class Database:
    def __init__(self):
        self.pool = ConnectionPool("dbname=veridash user=postgres")
        self.pool.open()


    def provision_object_name(self, user_id: int, filename: str) -> str:
        _, ext = path.splitext(filename)
        obj_name = str(uuid4()) + ext

        with self.pool.connection() as conn:
            conn.execute("INSERT INTO videos (owner_id, filename, object_name) VALUES (%s, %s, %s);",
                         (user_id, filename, obj_name))

        return obj_name


    def video_belongs_to_user(self, user_id: int, object_name: str) -> bool:
        with self.pool.connection() as conn:
            res = conn.execute("SELECT id FROM videos WHERE owner_id = %s AND object_name = %s;",
                               (user_id, object_name)).fetchone()

        return res is not None


    def get_cached_results(self, object_name: str, job_type: str) -> dict | None:
        with self.pool.connection() as conn:
            res = conn.execute("""
                SELECT r.job_result FROM job_results r
                INNER JOIN videos v on v.id = r.video_id
                WHERE r.job_type = %s
                AND v.hash_sha256 = (SELECT hash_sha256 FROM videos
                                     WHERE object_name = %s AND hash_sha256 is not null
                                     LIMIT 1)
                LIMIT 1;
                """, (job_type, object_name)).fetchone()

        return res


if __name__ == "__main__":
    db = Database()

