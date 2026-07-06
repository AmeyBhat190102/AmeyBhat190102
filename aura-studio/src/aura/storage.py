"""Flat-file artifact store. Interface is deliberately tiny so an S3/GCS
backend is a drop-in replacement when we outgrow local disk."""

from __future__ import annotations

from pathlib import Path


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, project_id: str, filename: str, data: bytes) -> str:
        path = self.root / project_id / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def load(self, path: str) -> bytes:
        return Path(path).read_bytes()
