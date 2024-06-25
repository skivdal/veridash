from fastapi import FastAPI, Request


app = FastAPI()


@app.get('/')
async def get_index(request: Request):
    return "Hello, world!"

