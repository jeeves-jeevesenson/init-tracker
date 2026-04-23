#!/usr/bin/env python3
import re
import sys
from collections import Counter

pattern = re.compile(r'LAN_PERF\s+([A-Za-z0-9_\.]+)')
counts = Counter()

for line in sys.stdin:
    m = pattern.search(line)
    if m:
        counts[m.group(1)] += 1

for name, count in counts.most_common():
    print(f"{name}: {count}")
