# simple db backed by a json file

from asyncio import sleep
import asyncio
import orjson
from pydantic import BaseModel


class DB:
    def __init__(self, path):
        self.path = path
        self.data: dict = self.load()
        self.save_task = None

    def load(self):
        try:
            with open(self.path, "r") as f:
                return orjson.loads(f.read())
        except FileNotFoundError:
            return {}

    def save(self):
        with open(self.path, "w") as f:
            f.write(orjson.dumps(self.data).decode())

    def get(self, key, default=None):
        return self.data.get(key, default)

    async def delayed_save(self):
        self.save_task = asyncio.current_task()
        await sleep(10)
        self.save_task = None
        self.save()

    def schedule_save(self):
        if self.save_task is None:
            asyncio.create_task(self.delayed_save())

    def set(self, key, value):
        if isinstance(value, BaseModel):
            value = value.dict()

        self.data[key] = value
        self.schedule_save()
