# RICO.CX

RICO.GA but the letter A is replaced with a Q but the letter G is replaced with a C but the letter Q is replaced with an X

## Project Structure

This repository is organized into two main directories:

- **`server/`** - Backend Flask application and server-side components
- **`Client/`** - Frontend client application

See the README files in each directory for more details.

## Quick Start

### Server

```bash
cd server
pip install -r requirements.txt
python app.py
```

### Client

```bash
cd Client
npm install
npm start
```

---
**Error code mapping:**

- APPLE:  508 - Failed to download the video (download)
- AVATAR: 508 - Failed to get video url (download)
- ASTRO:  508 - Failed to get video data (download)
- BANANA: 400 - No result provided for direct download link (download)
- BAGEL:  400 - No query provided (searchone)
- BANJO:  400 - No query provided (search)
- CHERRY: 404 - No results found (getvideo)
- DRAGON: 225 - Captcha failed (captcha)
- EAGLE:  500 - download.status is invalid (download_api)
- FALCON: 502 - Failed to communicate with the search service (search)
- GUITAR: 403 - Real-Debrid API key is invalid (realdebrid)
- HAMMER: 451 - Infringing video download (realdebrid)
- IGLOO:  
- JACKET:
- KETTLE:
- LEMON:  
- MONKEY:
- NINJA:  
- ORANGE:
- PANDA:  
