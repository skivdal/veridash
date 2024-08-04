from time import sleep
from contextlib import contextmanager
from redis import Redis


class LockManager:
    """
    Redis-based helper class to ensure single access to resources
    """
    def __init__(self):
        self.redis_client = Redis(host="localhost", port=6379, db=0)


    def acquire_lock(self, lock_name: str, data: str="TAKEN", expiration: int | None=3600) -> tuple[bool, str]:
        """
        :param lock_name: Unique lock identifier.
        :param data: Optional information associated with the lock
        :param expiration: Lock expiration time in seconds (None to never expire).
        :return: Tuple containing boolean indicating aquisition success, then string indicating lock data (current owners')
        """
        x = self.redis_client.set(lock_name, data, nx=True, ex=expiration, get=True)
        if x is None:
            return (True, data)
        return (False, str(x))


    def release_lock(self, lock_name: str):
        """
        :param lock_name: Unique lock identifier.
        """
        self.redis_client.delete(lock_name)


    @contextmanager
    def wait_for_lock(self, lock_name: str, data: str = "TAKEN", expiration: int | None=3600):
        """
        Wait for lock, acquiring it as soon as it becomes availiable
        :param lock_name: Unique lock identifier.
        :param data: Optional information associated with the lock
        :param expiration: Lock expiration time in seconds (None to never expire).
        :return: literal True on ownership acquired
        """
        owning = False
        while not owning:
            owning, _ = self.acquire_lock(lock_name, data, expiration)
            sleep(0.1)

        try:
            yield owning
        finally:
            self.release_lock(lock_name)

