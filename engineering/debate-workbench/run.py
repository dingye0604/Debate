"""Single-process local runner; explicit HTTPS reverse-proxy mode for hosting."""
import argparse
import ipaddress
import json
import socket
import threading
import urllib.request
import webbrowser
import uvicorn
from config import Settings
from app import create_app

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--remote-origin", help="Public HTTPS origin behind a trusted reverse proxy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--trusted-proxy", default="127.0.0.1", help="Single reverse proxy IP, never *")
    args = parser.parse_args()
    remote = bool(args.remote_origin)
    if not remote and args.host != "127.0.0.1":
        parser.error("Public binding requires --remote-origin with HTTPS.")
    try:
        ipaddress.ip_address(args.trusted_proxy)
        settings = Settings(origin=args.remote_origin or f"http://127.0.0.1:{args.port}", remote=remote)
    except ValueError as exc:
        parser.error(str(exc))
    url = settings.origin
    try:
        with socket.socket() as probe:
            probe.bind((args.host, args.port))
    except OSError:
        if not remote:
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(url + "/api/health", timeout=2) as response:
                    existing = json.load(response).get("app") == "debate-workbench"
                if existing:
                    print("Debate Workbench is already running: " + url)
                    if not args.no_browser:
                        webbrowser.open(url)
                    return
            except Exception:
                pass
        parser.error("Port unavailable. Choose another --port.")
    print("Debate Workbench: " + url, flush=True)
    if not args.no_browser and not remote:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(settings), host=args.host, port=args.port, workers=1,
                proxy_headers=remote, forwarded_allow_ips=args.trusted_proxy if remote else "",
                access_log=False, log_level="warning")

if __name__ == "__main__":
    main()
