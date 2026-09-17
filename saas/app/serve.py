#!/usr/bin/env python3
"""
serve.py — Gobob SOHO 服务平台静态服务 + API 反代

把 /api/* 转发到后端（默认 127.0.0.1:19001），其余走静态文件。
用法：SOHO_BACKEND=http://127.0.0.1:19001 python3 serve.py [port]
"""

import http.server
import os
import socketserver
import urllib.request
import urllib.error

BACKEND = os.environ.get("SOHO_BACKEND", "http://127.0.0.1:19001").rstrip("/")
PORT = int(os.environ.get("SOHO_APP_PORT", "19003"))
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _proxy(self):
        url = BACKEND + self.path
        body = None
        if self.command in ("POST", "PUT", "PATCH", "DELETE"):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
        req = urllib.request.Request(url, data=body, method=self.command)
        for k in ("Content-Type", "Authorization"):
            if self.headers.get(k):
                req.add_header(k, self.headers[k])
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as e:
            if e.code == 307:
                # FastAPI redirect_slashes: 去掉末尾 / 重试
                retry_url = url.rstrip("/")
                if retry_url == url:
                    self.send_response(e.code); self.end_headers(); return
                req2 = urllib.request.Request(retry_url, data=body, method=self.command)
                for k in ("Content-Type", "Authorization"):
                    if self.headers.get(k):
                        req2.add_header(k, self.headers[k])
                try:
                    with urllib.request.urlopen(req2, timeout=30) as resp:
                        payload = resp.read()
                        self.send_response(resp.status)
                        self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                        self.end_headers()
                        self.wfile.write(payload)
                    return
                except urllib.error.HTTPError as e2:
                    payload = e2.read()
                    self.send_response(e2.code); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(payload); return
                except Exception:
                    pass
            payload = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(('{"detail":"backend unreachable: %s"}' % str(e)[:120]).encode())

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        super().do_GET()

    def do_POST(self): return self._proxy()
    def do_PUT(self): return self._proxy()
    def do_DELETE(self): return self._proxy()

    def log_message(self, *a):  # 静音
        pass


if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"SOHO app serving on :{PORT}, proxying /api/* -> {BACKEND}")
        httpd.serve_forever()
