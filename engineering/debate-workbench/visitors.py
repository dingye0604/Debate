"""Cookie-scoped workspaces and expiring, process-memory-only credentials."""
import hashlib
import hmac
import re
import secrets
import time
from config import AppError
from engine import Engine
from store import Store
from model import Model
from search import Search

def owner_id(token):
    return hashlib.sha256(token.encode()).hexdigest()

def csrf(token):
    return hmac.new(token.encode(), b"debate-csrf-v2", hashlib.sha256).hexdigest()

class Visitors:
    def __init__(self, settings, provider, model_factory=None, search_factory=None):
        self.settings, self.provider = settings, provider
        self.root = settings.data / "workspaces"
        self.root.mkdir(parents=True, exist_ok=True)
        self.keys, self.engines, self.rates = {}, {}, {}
        self.model_factory, self.search_factory = model_factory, search_factory
        self.probing = set()

    def identify(self, token):
        if not token or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            return None
        owner = owner_id(token)
        return owner if (self.root / owner).is_dir() else None

    def create(self):
        token = secrets.token_urlsafe(32)
        (self.root / owner_id(token)).mkdir(exist_ok=False)
        return token

    def limit(self, key, count=60):
        now = time.monotonic()
        self.rates = {k: v for k, v in self.rates.items() if now - v[0] < 60}
        start, used = self.rates.get(key, (now, 0))
        if used >= count or (key not in self.rates and len(self.rates) > 10000):
            raise AppError("操作过于频繁，请稍后再试。")
        self.rates[key] = (start, used + 1)

    def purge(self):
        now = time.time()
        for owner, (_, expires) in list(self.keys.items()):
            if expires <= now:
                self.disconnect(owner)

    def require(self, owner):
        self.purge()
        if owner not in self.keys:
            raise AppError("请先连接你自己的模型 API；连接到期后需重新填写。")
        return self.keys[owner][0]

    def connected(self, owner):
        self.purge()
        item = self.keys.get(owner)
        return {"configured": bool(item), "expires": item[1] if item else None,
                "model": "已连接" if item else "连接你的模型"}

    def connect(self, owner, cfg):
        if self.engine(owner).tasks:
            raise AppError("请先暂停当前任务，再更换模型连接。")
        self.keys[owner] = (cfg, time.time() + self.settings.key_ttl)

    def disconnect(self, owner):
        self.keys.pop(owner, None)
        engine = self.engines.get(owner)
        if engine:
            for sid, task in list(engine.tasks.items()):
                task.cancel()
                s = engine.store.get(sid)
                s.update(status="paused", error="", revision=s["revision"] + 1)
                engine.store.save(s)

    def engine(self, owner):
        if owner not in self.engines:
            if len(self.engines) >= 256:
                for key, value in list(self.engines.items()):
                    if not value.tasks and key != owner:
                        self.engines.pop(key)
                        break
            store = Store(self.root / owner / "sessions")
            store.recover()
            model = self.model_factory(owner) if self.model_factory else Model(lambda: self.require(owner), self.provider)
            search = self.search_factory() if self.search_factory else Search(local=not self.settings.remote)
            self.engines[owner] = Engine(store, model, search)
        return self.engines[owner]

    def capacity(self, owner):
        self.require(owner)
        if self.engine(owner).tasks:
            raise AppError("你的另一个步骤仍在运行，请完成或暂停后继续。")
        if sum(len(e.tasks) for e in self.engines.values()) + len(self.probing) >= self.settings.max_jobs:
            raise AppError("工作台当前繁忙，请稍后重试。")
