"""
Aegis frontend demo server.
Serves the repo's web assets statically; proxies everything else (API) to the
local backend on 127.0.0.1:8741 so the new frontend renders real data.
"""
import http.server
import socketserver
import os
import sys
import urllib.request

# Resolve the web root relative to THIS script, so the demo server survives
# a repo rename/move (the old line hard-coded "aegis-ai-threat-monitor", which
# broke once the project folder was renamed to ai-aegis).
WEB = os.path.realpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "src", "aegis", "app", "assets", "web",
))
BACKEND = "http://127.0.0.1:8741"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
WEB_ROOT = os.path.realpath(WEB)

CTYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class Handler(http.server.BaseHTTPRequestHandler):
    def _handle(self, method):
        path = self.path.split("?")[0]
        rel = path.lstrip("/")
        if not rel:
            rel = "index.html"
        cand = os.path.realpath(os.path.join(WEB, rel.replace("/", os.sep)))
        if cand.startswith(WEB_ROOT) and os.path.isfile(cand):
            data = open(cand, "rb").read()
            ext = os.path.splitext(cand)[1].lower()
            self.send_response(200)
            self.send_header("Content-Type", CTYPES.get(ext, "application/octet-stream"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        # Proxy to backend (API endpoints, health, analyze, etc.)
        url = BACKEND + path
        if "?" in self.path:
            url += "?" + self.path.split("?", 1)[1]
        body = None
        if method in ("POST", "PUT", "PATCH"):
            ln = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(ln) if ln else None
        try:
            req = urllib.request.Request(url, data=body, method=method)
            for h in ("Content-Type", "Authorization", "X-Aegis-Device-Id"):
                if self.headers.get(h):
                    req.add_header(h, self.headers[h])
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type", r.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            payload = ('{"detail": "proxy error: %s"}' % e).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def do_PATCH(self):
        self._handle("PATCH")

    def log_message(self, *a):
        pass


class Server(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), Handler) as httpd:
        print("Aegis frontend demo on http://127.0.0.1:%d (proxy -> %s)" % (PORT, BACKEND))
        httpd.serve_forever()
