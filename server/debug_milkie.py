import requests
import urllib.parse
import os

def debug_milkie():
    # ID from previous run: HtXkpXyJlX7H
    # Guessing the endpoint based on REST patterns
    api_url = "https://milkie.cc/api/v1/torrents/HtXkpXyJlX7H"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9,es;q=0.8",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzA3NjI0NzQsImlhdCI6MTc2NTU3ODQ3NCwic3ViIjoiNTg4NTYifQ.QePsnSmLf_PIyGNjXWS2kmv-EZkvSccei7ESTwcRFQw",
        "dnt": "1",
        "priority": "u=1, i",
        "referer": "https://milkie.cc/browse",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.2.9) Gecko/20100915 Gentoo Firefox/3.6.9"
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Response Keys:", data.keys())
            if "magnet" in data:
                print("Magnet found:", data["magnet"])
            elif "hash" in data:
                print("Hash found:", data["hash"])
            else:
                print("No magnet/hash found. Full response:", data)
        else:
            print("Response:", response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_milkie()
