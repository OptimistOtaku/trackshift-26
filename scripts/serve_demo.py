"""Serve the offline demo plus grounded local-LLM Race Engineer.

python scripts/serve_demo.py --port 8000
Optional: set PITWALL_OLLAMA_MODEL to an already installed Ollama model name.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import threading
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pitwall.engineer import build_facts, commentary

CACHE = {}
LOCK = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if urlparse(self.path).path != "/api/engineer":
            self.send_error(404)
            return
        # Local endpoint, same-origin only. Client cannot supply arbitrary fact text.
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            self.send_error(403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2048:
                raise ValueError("Invalid request size")
            body = json.loads(self.rfile.read(length))
            rnd, lap, driver = body["round"], body["lap"], body["driver"]
            if (type(rnd) is not int or type(lap) is not int or not 1 <= rnd <= 99
                    or not isinstance(driver, str) or not driver.isalnum() or len(driver) > 6):
                raise ValueError("Invalid race cursor")
            facts = build_facts(ROOT, rnd, lap, driver)
            key = hashlib.sha256((json.dumps(facts, sort_keys=True)
                                  + os.environ.get("PITWALL_OLLAMA_MODEL", "")).encode()).hexdigest()
            with LOCK:
                result = CACHE.get(key)
            if result is None:
                result = commentary(facts)
                with LOCK:
                    if len(CACHE) >= 1024:
                        CACHE.clear()
                    CACHE[key] = result
            payload = json.dumps(dict(result, state_sha256=key)).encode()
        except (ValueError, KeyError, TypeError, FileNotFoundError):
            self.send_error(400, "Invalid or unavailable race state")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--llm-model", help="Already installed Ollama model; no download is performed")
    args = parser.parse_args()
    if args.llm_model:
        os.environ["PITWALL_OLLAMA_MODEL"] = args.llm_model
    handler = partial(Handler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"PITWALL: http://127.0.0.1:{args.port}/demo_fallback/", flush=True)
    server.serve_forever()
