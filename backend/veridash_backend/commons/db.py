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
            conn.execute("INSERT INTO videos (owner_id, filename, object_name) VALUES (%i, %s, %s);",
                         (user_id, filename, obj_name))

        return obj_name


if __name__ == "__main__":
    db = Database()

