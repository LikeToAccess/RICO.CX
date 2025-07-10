#!/usr/bin/env python3

from scraper import X1337
import json

print("Testing search functionality...")

scraper = X1337()
results = scraper.search('batman')[:2]  # Get just 2 results

for i, result in enumerate(results):
    data = result.sanatize()
    print(f'=== Result {i+1} ===')
    print(json.dumps(data, indent=2, default=str))
    print()
