"""Development-only database that stores records in JSON files.

It mimics the DynamoDB repositories method-for-method (same names, same return
values), so switching to AWS only means changing DB_BACKEND in .env.
"""
import json
import os
import threading
from pathlib import Path

from .common import title_matches, unique_subjects


class _JsonFile:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        if not self.path.exists():
            self.write({})

    def read(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def write(self, data):
        temp = self.path.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(temp, self.path)  # atomic swap avoids half-written files


class LocalUserRepository:
    def __init__(self, path):
        self._file = _JsonFile(path)

    def create(self, user):
        """Store a new user. Returns False if the email is already registered."""
        with self._file.lock:
            data = self._file.read()
            if user["email"] in data:
                return False
            data[user["email"]] = user
            self._file.write(data)
            return True

    def get_by_email(self, email):
        return self._file.read().get(email.strip().lower())


class LocalResourceRepository:
    def __init__(self, path):
        self._file = _JsonFile(path)

    def create(self, item):
        with self._file.lock:
            data = self._file.read()
            data[item["resource_id"]] = item
            self._file.write(data)

    def get(self, resource_id):
        return self._file.read().get(resource_id)

    def delete(self, resource_id):
        with self._file.lock:
            data = self._file.read()
            data.pop(resource_id, None)
            self._file.write(data)

    def _all_newest_first(self):
        return sorted(self._file.read().values(),
                      key=lambda item: item["uploaded_at"], reverse=True)

    def search(self, query=None, subject=None, category=None, limit=100):
        items = self._all_newest_first()
        if subject:
            items = [i for i in items if i["subject_key"] == subject.strip().lower()]
        if category:
            items = [i for i in items if i["category"] == category]
        items = [i for i in items if title_matches(i, query)]
        return items[:limit]

    def list_by_uploader(self, uploader_id, limit=100):
        items = [i for i in self._all_newest_first() if i["uploader_id"] == uploader_id]
        return items[:limit]

    def list_subjects(self):
        return unique_subjects(self._all_newest_first())
