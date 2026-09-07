"""Two explicit BYOK protocol adapters; no machine-level credential fallback."""
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from config import AppError
import network

@dataclass(frozen=True, repr=False)
class Profile:
    protocol: str
    base: str
    model: str
    key: str = field(repr=False)

def profile(protocol, base, model, key):
    base, model, key = base.strip().rstrip("/"), model.strip(), key.strip()
    try:
        p = urlsplit(base)
        if protocol not in ("openai", "anthropic") or p.scheme != "https" or not p.hostname or p.username or p.password or p.query or p.fragment or p.port not in (None, 443):
            raise ValueError()
        if not model or len(model) > 200 or not key or len(key) > 4096 or any(ord(c) < 32 or ord(c) > 126 for c in key):
            raise ValueError()
    except ValueError:
        raise AppError("请填写有效的 HTTPS Base URL、模型 ID 和 API Key。") from None
    return Profile(protocol, base, model, key)

class Provider:
    def __init__(self, local=False, sender=None):
        self.local = local
        self.sender = sender or network.request

    async def request(self, cfg, system, prompt, max_tokens=7000, schema=None):
        base = cfg.base
        suffix = "/messages" if cfg.protocol == "anthropic" else "/chat/completions"
        url = base + suffix if base.endswith("/v1") else base + "/v1" + suffix
        headers = {"Authorization": "Bearer " + cfg.key}
        if cfg.protocol == "anthropic":
            headers.update({"x-api-key": cfg.key, "anthropic-version": "2023-06-01"})
            payload = {"model": cfg.model, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role": "user", "content": prompt}]}
        else:
            token_field = "max_completion_tokens" if urlsplit(base).hostname == "api.openai.com" else "max_tokens"
            payload = {"model": cfg.model, token_field: max_tokens,
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        # Prompt-based JSON keeps compatibility with gateways without structured-output extensions.
        # The workflow validates every response strictly before persisting it.
        response = await self.sender("POST", url, local=self.local, api=True, headers=headers, payload=payload)
        if response.status_code != 200:
            messages = {400: "模型不接受当前参数", 401: "密钥无效或已过期", 403: "模型接口拒绝访问",
                        404: "接口地址或模型 ID 不存在", 429: "请求频繁或额度不足"}
            raise AppError(messages.get(response.status_code, "模型服务暂时不可用") + "。请检查模型设置后重试。")
        try:
            data = response.json()
            usage = data.get("usage", {})
            if cfg.protocol == "anthropic":
                stopped = data.get("stop_reason") == "max_tokens"
                content = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
                counts = (usage.get("input_tokens", 0), usage.get("output_tokens", 0))
            else:
                choice = data["choices"][0]
                stopped = choice.get("finish_reason") == "length"
                content = choice["message"]["content"]
                counts = (usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            if stopped:
                raise AppError("模型输出达到长度限制，进度未推进。请缩小讨论范围后重试。")
            if not isinstance(content, str) or not content.strip():
                raise ValueError()
            content = content.replace(cfg.key, "[已隐藏]")
            return content, dict(zip(("input_tokens", "output_tokens"), (int(x or 0) for x in counts)))
        except (ValueError, KeyError, TypeError, IndexError):
            raise AppError("模型响应格式不受支持，请检查协议或更换模型。") from None

    async def probe(self, cfg):
        await self.request(cfg, "You are a connection test. Reply OK.", "Reply OK.", max_tokens=256)
