#!/usr/bin/env python3
"""Check the public MCP routes and the viewer backends without printing credentials."""
import base64
import http.client
import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path

APP = Path("/opt/aibrowser")
DOMAIN = (APP / "domain").read_text().strip()


def status(path):
    try:
        with urllib.request.urlopen(f"https://{DOMAIN}{path}", timeout=10) as reply:
            return reply.status
    except urllib.error.HTTPError as reply:
        return reply.code


def check_connector(lane):
    secret = (APP / "keys" / lane).read_text().strip()
    initialization = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "sumopod-verification", "version": "1"},
        },
    }
    request = urllib.request.Request(
        f"https://{DOMAIN}/{secret}/mcp",
        json.dumps(initialization).encode(),
        {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    with urllib.request.urlopen(request, timeout=15) as reply:
        if reply.headers.get_content_type() == "text/event-stream":
            result = next(json.loads(line[6:]) for line in reply if line.startswith(b"data: "))
        else:
            result = json.load(reply)
        assert "serverInfo" in result["result"], "MCP initialization failed"


def check_viewer_backend(port):
    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        key = base64.b64encode(os.urandom(16)).decode()
        connection.sendall((
            f"GET /websockify HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            "Connection: Upgrade\r\nUpgrade: websocket\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Protocol: binary\r\n\r\n"
        ).encode())
        reply = http.client.HTTPResponse(connection)
        reply.begin()
        assert reply.status == 101, "noVNC WebSocket upgrade failed"
        banner = connection.makefile("rb") if reply.fp is None else reply.fp
        try:
            assert b"RFB " in banner.read(14), "VNC server handshake failed"
        finally:
            banner.close()


def main():
    assert status("/mcp") == 404, "Unprotected MCP route must return 404"
    for lane, viewer_port in (("claude", 6081), ("chatgpt", 6082)):
        assert status(f"/view-{lane}/vnc.html") == 401, "Viewer page must require a password"
        assert status(f"/view-{lane}/websockify") == 401, "Viewer socket must require a password"
        check_connector(lane)
        check_viewer_backend(viewer_port)
        print(f"{lane}: HTTPS MCP initialized, viewer requires login, VNC handshake passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Verification failed: {type(error).__name__}")
        raise SystemExit(1) from None
