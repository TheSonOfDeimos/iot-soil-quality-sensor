import ujson
import os

from logger import log

class JsonFileUtil:
    def __init__(self, path: str):
        self.path = path

    def read(self, default=None):
        try:
            with open(self.path, "r") as f:
                data = ujson.load(f)
            log.debug(f"Loaded JSON from {self.path}: {data}")
            return data
        except OSError:
            log.debug(f"No file found: {self.path}")
            return default
        except ValueError as e:
            log.debug(f"Invalid JSON in {self.path}: {e}")
            return default

    def rewrite(self, obj):
        try:
            with open(self.path, "w") as f:
                ujson.dump(obj, f)
            log.debug(f"Wrote JSON to {self.path}: {obj}")
        except OSError as e:
            log.debug(f"Error writing {self.path}: {e}")
            raise

    def delete(self) -> bool:
        try:
            os.remove(self.path)
            log.debug(f"Deleted file: {self.path}")
            return True
        except OSError:
            log.debug(f"No file to delete: {self.path}")
            return False
