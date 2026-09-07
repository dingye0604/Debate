"""Runtime settings only. Never import a developer's model credentials."""
import os
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DEBATE_DATA_DIR", ROOT / "data"))

class AppError(Exception):
    pass

@dataclass(frozen=True)
class Settings:
    data: Path = DATA
    origin: str = "http://127.0.0.1:8766"
    remote: bool = False
    key_ttl: int = 7200
    max_jobs: int = 4

    def __post_init__(self):
        p = urlsplit(self.origin)
        if not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ("", "/"):
            raise ValueError("Invalid public origin")
        if self.remote and (p.scheme != "https" or p.hostname in ("localhost", "127.0.0.1")):
            raise ValueError("Remote mode requires a public HTTPS origin")
        if not self.remote and (p.scheme != "http" or p.hostname not in ("127.0.0.1", "localhost", "testserver")):
            raise ValueError("Local mode requires a loopback origin")

    @property
    def cookie(self):
        return "__Host-debate" if self.remote else "debate_visitor"
