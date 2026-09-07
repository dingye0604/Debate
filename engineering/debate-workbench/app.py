import asyncio
import hmac
import mimetypes
from contextlib import asynccontextmanager, suppress
from urllib.parse import quote, urlsplit
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ConfigDict
from config import ROOT, AppError, Settings
from provider import Provider, profile
from visitors import Visitors, csrf
from documents import documents, merged, zip_bytes

mimetypes.add_type("application/javascript", ".mjs")

class NewSession(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    topic: str = Field(min_length=4, max_length=600)
    side: str = Field(pattern="^(正方|反方)$")
    format: str = Field(default="", max_length=100)
    date: str = Field(default="", max_length=20)

class Action(BaseModel):
    action: str = Field(max_length=20)
    revision: int = Field(ge=0)
    text: str = Field(default="", max_length=12000)
    target: int | None = None

class Connection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol: str = Field(max_length=20)
    base: str = Field(max_length=1000)
    model: str = Field(max_length=200)
    key: str = Field(max_length=4096, repr=False)

def create_app(settings=None, provider=None, model_factory=None, search_factory=None):
    settings = settings or Settings()
    visitors = Visitors(settings, provider or Provider(local=not settings.remote), model_factory, search_factory)

    @asynccontextmanager
    async def lifespan(app):
        async def cleanup():
            while True:
                await asyncio.sleep(30)
                visitors.purge()
        timer = asyncio.create_task(cleanup())
        yield
        timer.cancel()
        with suppress(asyncio.CancelledError):
            await timer
        jobs = [task for engine in visitors.engines.values() for task in engine.tasks.values()]
        for owner in list(visitors.engines):
            visitors.disconnect(owner)
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        visitors.keys.clear()

    app = FastAPI(title="辩序 · 备赛工作台", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.visitors = visitors
    app.state.settings = settings
    hosts = [urlsplit(settings.origin).hostname] if settings.remote else ["127.0.0.1", "localhost", "testserver"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        def reject(message, status):
            return JSONResponse({"error": message}, status_code=status)
        if settings.remote and request.url.scheme != "https":
            return reject("远端工作台仅接受 HTTPS 请求。", 403)
        if request.url.path.startswith("/api/") and request.url.path not in ("/api/config", "/api/health"):
            owner = visitors.identify(request.cookies.get(settings.cookie))
            if not owner:
                return reject("访客空间已失效，请刷新页面重新进入。", 401)
            request.state.owner = owner
        if request.method not in ("GET", "HEAD"):
            origin = request.headers.get("origin")
            expected = settings.origin.rstrip("/") if settings.remote else str(request.base_url).rstrip("/")
            token = request.cookies.get(settings.cookie, "")
            if (origin and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
                return reject("操作必须来自当前工作台页面。", 403)
            if request.headers.get("x-debate-client") != "workbench" or not token or not hmac.compare_digest(request.headers.get("x-csrf-token", ""), csrf(token)):
                return reject("页面校验已失效，请刷新后重试。", 403)
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 50000:
                    return reject("输入超过大小限制。", 413)
            request._body = bytes(raw)
        response = await call_next(request)
        response.headers.update({
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        })
        if settings.remote:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(AppError)
    async def expected_error(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Pydantic's default input echo may contain an API key.
        return JSONResponse({"error": "输入格式或长度不符合要求，请检查表单。"}, status_code=422)

    @app.get("/api/health")
    def health():
        return {"app": "debate-workbench", "version": "2.0"}

    @app.get("/api/config")
    async def config(request: Request):
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"error": "请从工作台页面进入。"}, status_code=403)
        token = request.cookies.get(settings.cookie)
        owner = visitors.identify(token)
        if not owner:
            visitors.limit("new:" + (request.client.host if request.client else "unknown"), 10)
            token = visitors.create()
            owner = visitors.identify(token)
        result = JSONResponse({**visitors.connected(owner), "csrf": csrf(token), "workspace": owner[:16],
                               "mode": "remote" if settings.remote else "local"})
        result.set_cookie(settings.cookie, token, max_age=30*86400, httponly=True, secure=settings.remote, samesite="lax", path="/")
        return result

    @app.post("/api/connection/{operation}")
    async def connection(request: Request, operation: str, body: Connection):
        owner = request.state.owner
        if operation not in ("test", "connect"):
            raise AppError("无效的连接操作。")
        visitors.limit("connect:" + owner, 8)
        if owner in visitors.probing or visitors.engine(owner).tasks:
            raise AppError("请等待连接测试结束，或先暂停当前备赛。")
        if len(visitors.probing) + sum(len(e.tasks) for e in visitors.engines.values()) >= settings.max_jobs:
            raise AppError("工作台当前繁忙，请稍后重试。")
        cfg = profile(body.protocol, body.base, body.model, body.key)
        visitors.probing.add(owner)
        try:
            await visitors.provider.probe(cfg)
            if operation == "connect":
                visitors.connect(owner, cfg)
        finally:
            visitors.probing.discard(owner)
        return {**visitors.connected(owner), "message": "连接测试通过" if operation == "test" else "模型已连接，有效期两小时"}

    @app.post("/api/disconnect")
    async def disconnect(request: Request):
        owner = request.state.owner
        if owner in visitors.probing:
            raise AppError("连接测试尚未结束，请等待后断开。")
        visitors.disconnect(owner)
        return visitors.connected(owner)

    @app.get("/api/sessions")
    async def sessions(request: Request):
        return visitors.engine(request.state.owner).store.list()

    @app.post("/api/sessions")
    async def create_session(request: Request, body: NewSession):
        owner = request.state.owner
        visitors.limit("action:" + owner, 30)
        visitors.capacity(owner)
        engine = visitors.engine(owner)
        if len(engine.store.list()) >= 50:
            raise AppError("当前空间已达到 50 份档案上限，请联系工作台维护者。")
        return engine.start(engine.store.create(body.topic, body.side, body.format, body.date))

    @app.get("/api/sessions/{sid}")
    async def session(request: Request, sid: str):
        engine = visitors.engine(request.state.owner)
        return engine.view(engine.store.get(sid))

    @app.post("/api/sessions/{sid}/action")
    async def action(request: Request, sid: str, body: Action):
        owner = request.state.owner
        engine = visitors.engine(owner)
        s = engine.store.get(sid)  # Ownership before credential checks or mutations.
        visitors.limit("action:" + owner, 30)
        if body.action != "pause":
            visitors.capacity(owner)
            if len(s["history"]) >= 600 or len(s["sources"]) >= 240:
                raise AppError("此档案已达到交互或资料上限，请下载后新建备赛。")
        return engine.action(sid, body.action, body.revision, body.text, body.target)

    @app.get("/api/sessions/{sid}/download/{kind}")
    async def download(request: Request, sid: str, kind: str):
        s = visitors.engine(request.state.owner).store.get(sid)
        if kind == "zip":
            content, filename, media = zip_bytes(s), "备赛档案.zip", "application/zip"
        elif kind == "merged":
            content, filename, media = merged(s).encode("utf-8-sig"), "备赛总档案.md", "text/markdown"
        elif kind in ("0", "1", "2", "3", "4"):
            doc = documents(s)[int(kind)]
            content, filename, media = doc["content"].encode("utf-8-sig"), doc["name"], "text/markdown"
        else:
            raise AppError("无效的下载类型。")
        return Response(content, media_type=media, headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename)})

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.get("/")
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    return app

app = create_app()
