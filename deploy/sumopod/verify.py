import asyncio
import sqlite3
import urllib.request
import urllib.error
import websockets

base = "https://openc.43.173.40.109.sslip.io"
for path in ["/", "/auth", "/api/config", "/api/v1/chats/"]:
    try:
        request = urllib.request.Request(base + path, headers={"Accept-Encoding": "gzip"})
        with urllib.request.urlopen(request, timeout=15) as response:
            print("HTTP", path, response.status, "encoding", response.headers.get("Content-Encoding"))
    except urllib.error.HTTPError as error:
        if path != "/api/v1/chats/" or error.code != 401:
            raise
        print("AUTH_PROTECTION_OK", error.code)
connection = sqlite3.connect("file:/app/backend/data/webui.db?mode=ro", uri=True)
print("USERS", connection.execute("select count(*) from user").fetchone()[0])
print("CHATS", connection.execute("select count(*) from chat").fetchone()[0])
async def check():
    async with websockets.connect(
        base.replace("https://", "wss://") + "/ws/socket.io/?EIO=4&transport=websocket",
        origin=base
    ) as socket:
        assert (await socket.recv()).startswith("0")
        print("SAME_ORIGIN_WEBSOCKET_OK")
asyncio.run(check())
