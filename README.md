# RICO.CX v4

RICO.CX v4 is a high-performance, automated media search and download manager that integrates indexers (Prowlarr), debrid cloud acceleration (Torbox), and metadata enrichment (The Movie Database / TMDb) to automatically curate, rename, and mirror media locally.

It features a responsive, dark-themed Single Page Application (SPA) dashboard for executing searches, queueing cloud transfers, monitoring downloads in real time via WebSockets, and organizing media into a structured, Plex/Jellyfin-compatible library.

---

## Key Features

- **Unified Media & Direct Magnet Search**:
  - Direct multi-indexer search across Usenet and torrent indexers via Prowlarr.
  - Direct InfoHash (hex/base32) and raw `magnet:` URI input with instant cloud resolution.
- **Server Presence & Version Overwrite**:
  - Real-time indicators on search result cards (`ON SERVER`) identifying media already present in your library.
  - Granular release-level status and seamless support for upgrading versions (e.g., replacing CAM releases with 1080p/4K HDR WEB-DLs).
- **TMDb Metadata & Artwork Resolution**:
  - Enriches media with high-resolution posters, canonical release years, genres, and exact episode titles.
- **Debrid Cloud Acceleration**:
  - Queues downloads directly to cloud storage at high speeds with real-time transfer tracking.
- **Automated Local Library Mirroring & Curation**:
  - A persistent background worker automatically streams and verifies completed video files to local storage.
  - Automatic directory formatting and clean file renaming:
    - **Movies**: `MOVIES/Title (Year) {tmdb-ID}/Title (Year) {tmdb-ID}.ext`
    - **TV Shows**: `TV SHOWS/Show Title (Year) {tmdb-ID}/Season XX/Show Title (Year) - SXXEXX - Episode Title.ext`
- **Real-Time WebSocket Telemetry**:
  - Throttled, low-latency progress, speed, and transfer status updates via `Socket.IO`.
- **System Administration & Live Monitoring**:
  - Multi-tier group access controls (**Admin**, **Moderator**, **User**, **Pending Approval**).
  - Live system telemetry dashboard reporting SQLite database size, WAL file metrics, library storage capacity, and user activity sorted by most recent downloads.
- **Home Assistant Alert Integrations**:
  - Instant push notifications and persistent alerts dispatched on service interruptions, startup recovery, and new user approval requests formatted in local time.
- **Crash Recovery & Resumption**:
  - Automatic download resumption upon service restart or system crash.

---

## Technology Stack

- **Backend**: Python 3.10+ (Flask, Flask-SocketIO, gevent, requests, python-dotenv)
- **Frontend**: Vanilla HTML5, CSS3, ES6 JavaScript (No compilation or build step required)
- **Database**: SQLite3 (configured in WAL journal mode with automated schema migrations)
- **Real-Time Communication**: WebSocket transport via Socket.IO

---

## Project Structure

```
P121 - RICO.CX v4/
├── backend/
│   ├── models/            # Relational models (User, Group, Result)
│   ├── routes/            # Blueprint API endpoints and auth controllers (api.py)
│   ├── services/          # Integration clients (Prowlarr, Torbox, TMDb, Caches)
│   ├── utils/             # Helper utilities and formatters
│   ├── app.py             # Application factory & SocketIO server setup
│   └── database.py        # SQLite interface and migration runner
├── frontend/              # Web application client (SPA)
│   ├── fonts/             # Custom typography
│   ├── index.html         # Application entry point
│   ├── index.css          # Cyber-styled design system
│   ├── main.js            # Frontend state router and socket handler
│   └── socket.io.esm.min.js
├── tests/                 # Unit and integration test suite
├── main.py                # Server execution entry point
├── schema.sql             # Relational SQL database schema
├── requirements.txt       # Production dependencies
└── LICENSE                # MIT License
```

---

## Configuration & Environment Variables

Create a `.env` file in the project root to configure the application environment:

| Variable | Description | Default |
|:---|:---|:---|
| `PORT` | Web server listening port. | `5000` |
| `DEBUG_MODE` | Enable or disable Flask debug mode (`True`/`False`). | `False` |
| `USE_SSL` | Enable ad-hoc SSL encryption (`True`/`False`). | `False` |
| `DATABASE_PATH` | File path to the SQLite database. | `database.db` |
| `FLASK_SECRET_KEY` | Secret key used for cryptographic session signing. | *Generated* |
| `PROWLARR_URL` | Base URL of your Prowlarr instance. | `http://localhost:9696` |
| `PROWLARR_API_KEY` | API Key for Prowlarr authentication. | *None* |
| `TORBOX_API_KEY` | API Key for Torbox cloud debrid client. | *None* |
| `TMDB_API_KEY` | API Key for The Movie Database API. | *None* |
| `ROOT_LIBRARY_LOCATION` | Local filesystem path for stored media. | `./library` |
| `GOOGLE_CLIENT_ID` | Google Cloud Console OAuth Client ID. | *None* |
| `GOOGLE_CLIENT_SECRET` | Google Cloud Console OAuth Client Secret. | *None* |
| `HA_WEBHOOK_URL` | Home Assistant webhook URL for automated alerts. | *None* |

---

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
- A running **Prowlarr** instance (for torrent and Usenet indexer queries)
- **Torbox** API Key
- **TMDb** API Key
- **Google Cloud Console** OAuth 2.0 Client Credentials

### Step-by-Step Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/LikeToAccess/RICO.CX.git
   cd "P121 - RICO.CX v4"
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file and define the required API keys and configuration parameters (refer to the [Configuration](#configuration--environment-variables) section).

4. **Start the Server**:
   ```bash
   python3 main.py
   ```

5. **Access the Web Dashboard**:
   Open your browser and navigate to `http://localhost:5000` (or `https://localhost:5000` when SSL is enabled).

---

## Authentication & Initial Admin Setup

RICO.CX uses a secure, multi-tier group authorization system:

- **Admin**: Full access to global server settings, library storage metrics, user approval management, and all system downloads.
- **Moderator**: Access to server-wide downloads and read-only user listings.
- **User**: Search media, initiate downloads, and manage individual transfers.
- **Pending Approval**: Newly registered users awaiting administrative authorization.

### Seeding the First Admin Account
1. Starting with an unpopulated database, initialize the application.
2. The **first user** to authenticate via Google OAuth automatically receives the **Admin** role.
3. Subsequent logins are assigned to **Pending Approval**.
4. The Admin can navigate to the **Admin Panel -> Users Directory** to grant approvals and modify roles.

---

## Testing & Quality Assurance

Run the test suite using Python's `unittest` framework:

```bash
python3 -m unittest discover tests
```

To run static type checking:

```bash
mypy main.py backend/ tests/
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
