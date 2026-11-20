import collections
import os
from pathlib import Path
from collections import Counter
limits = Path("/proc/1/limits").read_text()
print(next(line for line in limits.splitlines() if line.startswith("Max open files")))
counts = Counter()
for entry in Path("/proc/1/fd").iterdir():
    try:
        target = os.readlink(entry)
    except OSError:
        continue
    if target.startswith("socket:"):
        kind = "sockets"
    elif "webui.db" in target:
        kind = "sqlite"
    elif target.startswith("anon_inode:"):
        kind = "anonymous"
    elif target.startswith("pipe:"):
        kind = "pipes"
    else:
        kind = "other_files"
    counts[kind] += 1
print("FD_TOTAL", sum(counts.values()), dict(counts))
