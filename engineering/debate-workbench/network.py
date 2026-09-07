"""Resolve, validate and pin outbound destinations before opening a connection."""
import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit
import httpx
from config import AppError

def resolve(url, local=False, api=False):
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower().rstrip(".")
        port = p.port or (443 if p.scheme == "https" else 80)
        if p.scheme not in (("https",) if api else ("http", "https")) or not host or p.username or p.password:
            raise ValueError()
        if port not in ((443,) if api else (80, 443)) or p.fragment or (api and p.query):
            raise ValueError()
        if "." not in host or host.endswith((".local", ".localhost", ".internal", ".lan", ".home", ".test")):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        def allowed(value):
            ip = ipaddress.ip_address(value)
            return ip.is_global or (local and ip.version == 4 and ip in ipaddress.ip_network("198.18.0.0/15"))
        if not addresses or any(not allowed(a[4][0]) for a in addresses):
            raise ValueError()
        return host, addresses[0][4][0]
    except (ValueError, OSError):
        raise AppError("地址必须是可访问的公网域名；模型接口须使用 HTTPS 和标准端口。") from None

async def request(method, url, *, local=False, api=False, headers=None, payload=None, limit=2000000):
    try:
        async with asyncio.timeout(150 if api else 18):
            host, address = await asyncio.wait_for(asyncio.to_thread(resolve, url, local, api), 6)
            original = httpx.URL(url)
            pinned = original.copy_with(host=address)
            request_headers = dict(headers or {})
            request_headers["Host"] = original.netloc.decode("ascii")
            async with httpx.AsyncClient(timeout=httpx.Timeout(120 if api else 12, connect=12),
                                         trust_env=False, follow_redirects=False) as client:
                req = client.build_request(method, pinned, headers=request_headers, json=payload if payload is not None else None)
                req.extensions["sni_hostname"] = host
                response = await client.send(req, stream=True)
                try:
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw) + len(chunk) > limit:
                            raise AppError("远端响应超过大小限制，请缩小讨论范围后重试。")
                        raw.extend(chunk)
                    clean_headers = {k: v for k, v in response.headers.items() if k.lower() not in ("content-encoding", "content-length")}
                    return httpx.Response(response.status_code, headers=clean_headers, content=bytes(raw), request=httpx.Request(method, url))
                finally:
                    await response.aclose()
    except AppError:
        raise
    except (httpx.HTTPError, TimeoutError, ValueError, OSError):
        raise AppError("连接失败或超时，请检查接口地址和网络后重试。") from None
