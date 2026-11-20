from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request

def count():
    return len(list(Path("/proc/1/fd").iterdir()))

def request(_):
    with urllib.request.urlopen("http://127.0.0.1:8080/api/config", timeout=30) as response:
        assert response.status == 200
        response.read()

before = count()
with ThreadPoolExecutor(max_workers=8) as executor:
    list(executor.map(request, range(80)))
after = count()
print("API_REQUESTS_OK", 80, "FD_BEFORE", before, "FD_AFTER", after)
assert after < 256, "Unexpected file-handle growth"
