#!/usr/bin/env python3

import requests
import json

print("Testing API endpoint...")

try:
    # Test the API endpoint directly
    response = requests.get('https://127.0.0.1:9000/api/v2/search?q=batman', verify=False)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Number of results: {len(data)}")
        if data:
            print("\n=== First Result ===")
            print(json.dumps(data[0], indent=2, default=str))
    else:
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"Exception: {e}")
