import time
from celery import Celery

app = Celery('worker', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0',
             broker_connection_retry_on_startup=True)


@app.task(bind=True)
def long_task(self, x, y):
    time.sleep(2)  # Simulate a long task
    return {"value": x + y}

