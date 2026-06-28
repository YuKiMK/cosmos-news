#!/usr/bin/env python3
"""
Cosmos local web server
- Serves 科学情報.html to any device on the same WiFi
- Handles /update endpoint for the manual update button

Access from PC:     http://localhost:8080
Access from iPad:   http://[PCのIPアドレス]:8080
  (IPアドレスは起動時に画面に表示されます)

Start: double-click run_server.bat
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import threading
import json
import sys
import socket
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
HTML_FILE  = SCRIPT_DIR / "科学情報.html"
PORT = 8080
_updating = False

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # suppress access logs

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._json({})

    def do_GET(self):
        global _updating

        # ── /update : trigger article regeneration ────────────────────────
        if self.path == "/update":
            if _updating:
                self._json({"status": "already_running"})
                return

            def run():
                global _updating
                _updating = True
                try:
                    for edition in ["morning", "evening"]:
                        subprocess.run(
                            [sys.executable,
                             str(SCRIPT_DIR / "update_news.py"),
                             "--edition", edition],
                            cwd=str(SCRIPT_DIR)
                        )
                finally:
                    _updating = False

            threading.Thread(target=run, daemon=True).start()
            self._json({"status": "started"})

        # ── /status : check if update is running ──────────────────────────
        elif self.path == "/status":
            self._json({"updating": _updating})

        # ── / or /科学情報.html : serve the main page ──────────────────────
        elif self.path in ("/", "/index.html", "/%E7%A7%91%E5%AD%A6%E6%83%85%E5%A0%B1.html"):
            if not HTML_FILE.exists():
                self.send_response(404)
                self.end_headers()
                return
            content = HTML_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    ip = get_local_ip()
    print("=" * 52)
    print("  Cosmos News サーバー起動中")
    print("=" * 52)
    print(f"  PC・このブラウザ: http://localhost:{PORT}")
    print(f"  iPad・スマホ:     http://{ip}:{PORT}")
    print()
    print("  ※ iPad・スマホは同じWiFiに接続してください")
    print("  ※ このウィンドウを閉じるとサーバーが停止します")
    print("=" * 52)
    try:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nサーバーを停止しました。")
