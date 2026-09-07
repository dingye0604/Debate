"""Bounded public-web retrieval. Retrieved text is not a truth certification."""
import asyncio
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse
import httpx
from config import AppError

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())

def public_url(url, local=True):
    from network import resolve
    return resolve(url, local=local)

async def fetch_text(url, local=False):
    from network import request
    from urllib.parse import urljoin
    try:
        for _ in range(4):
            response = await request("GET", url, local=local, limit=350000,
                                     headers={"User-Agent": "Mozilla/5.0 (compatible; DebateWorkbench/2.0)"})
            if response.is_redirect:
                url = urljoin(url, response.headers.get("location", ""))
                continue
            response.raise_for_status()
            if not any(t in response.headers.get("content-type", "") for t in ("text/html", "text/plain")):
                return ""
            parser = TextParser()
            parser.feed(response.text)
            return " ".join(parser.parts)[:5000]
    except Exception:
        return ""
    return ""

def web_search(query):
    from ddgs import DDGS
    try:
        return list(DDGS(timeout=10).text(query, region="cn-zh", max_results=4))
    except Exception:
        return []

class Search:
    def __init__(self, local=False):
        self.local = local

    async def run(self, queries):
        async def one(query):
            try:
                found = await asyncio.wait_for(asyncio.to_thread(web_search, query), timeout=35)
            except asyncio.TimeoutError:
                found = []
            results = []
            for row in found[:4]:
                url = row.get("href") or row.get("url", "")
                if not url.startswith(("https://", "http://")):
                    continue
                results.append({"title": str(row.get("title", "来源"))[:300], "url": url,
                                "snippet": str(row.get("body", ""))[:1800], "text": "", "query": query,
                                "status": "仅搜索摘要，未核验原文"})
            # Fetch the first two candidates per query; bound network and context size.
            texts = await asyncio.gather(*(fetch_text(row["url"], self.local) for row in results[:2]))
            for row, text in zip(results, texts):
                if len(text) > 180:
                    row["text"] = text[:3000]
                    row["status"] = "已获取网页正文，观点仍需核验"
            return {"query": query, "count": len(results)}, results
        pairs = await asyncio.gather(*(one(q) for q in queries[:3]))
        runs, sources = [], []
        seen = set()
        for run, rows in pairs:
            runs.append(run)
            for row in rows:
                if row["url"] not in seen:
                    sources.append(row)
                    seen.add(row["url"])
        return runs, sources
