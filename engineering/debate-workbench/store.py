import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from config import AppError, DATA

def now():
    return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, root=None):
        self.root = Path(root or DATA / "sessions")
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def folder(self, sid):
        if not re.fullmatch(r"[a-f0-9]{32}", sid):
            raise AppError("无效的备赛编号。")
        return self.root / sid

    def save(self, session):
        with self.lock:
            folder = self.folder(session["id"])
            folder.mkdir(parents=True, exist_ok=True)
            session["updated"] = now()
            temp = folder / "session.tmp"
            temp.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(folder / "session.json")

    def get(self, sid):
        with self.lock:
            try:
                return json.loads((self.folder(sid) / "session.json").read_text(encoding="utf-8"))
            except FileNotFoundError:
                raise AppError("未找到这场备赛。") from None

    def create(self, topic, side, format_name, date):
        s = {"id": uuid.uuid4().hex, "topic": topic, "side": side, "format": format_name,
             "date": date, "created": now(), "updated": now(), "index": 0, "revision": 0,
             "status": "idle", "error": "", "nodes": {}, "history": [], "sources": [],
             "search_runs": [], "usage": {"input_tokens": 0, "output_tokens": 0}, "pending": None}
        self.save(s)
        return s

    def archive(self, s):
        folder = self.folder(s["id"]) / "versions"
        folder.mkdir(exist_ok=True)
        (folder / f"{s['revision']:05d}-{uuid.uuid4().hex[:8]}.json").write_text(
            json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self):
        result = []
        for path in self.root.glob("*/session.json"):
            try:
                s = self.get(path.parent.name)
                result.append({k: s[k] for k in ("id", "topic", "side", "updated", "index", "status")})
            except (AppError, ValueError, KeyError):
                continue
        return sorted(result, key=lambda s: s["updated"], reverse=True)

    def recover(self):
        for item in self.list():
            s = self.get(item["id"])
            if s["status"] == "running":
                s["status"] = "error"
                s["error"] = "上次运行随服务关闭而中断。已保存之前的内容，可以重试。"
                self.save(s)
