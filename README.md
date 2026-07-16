# RICO.CX v4

RICO.CX v4 is a private, automated media-downloader interface leveraging debrid integrations, Prowlarr indexers, and TMDb metadata to curate, rename, and mirror media locally. It provides a beautiful, dark-themed dashboard to search for media, queue remote downloads, monitor progress in real-time, and automatically organize downloaded movies and TV shows into a structured Plex/Jellyfin-compatible media library.

---

## 🚀 Key Features

* **Unified Media Search**: Integrates with Prowlarr to search across public/private Usenet and indexer resources simultaneously.
* **TMDb Integration**: Enriches search results and files with posters, official titles, release years, and episode titles from [The Movie Database (TMDb)](https://www.themoviedb.org/).
* **Debrid-Powered Downloads**: Downloads search results and magnet/file links at ultra-fast cloud speeds using the integrated debrid API client.
* **Local Library Syncing**: A background worker monitors cloud transfers and automatically downloads finished video files to local storage.
* **Automated Curation & Renaming**: Automatically parses releases and organizes them into standard media server directories:
  * **Movies**: `MOVIES/Movie Title (Year) {tmdb-ID}/Movie Title (Year) {tmdb-ID}.ext`
  * **TV Shows**: `TV SHOWS/Show Title (Year) {tmdb-ID}/Season XX/Show Title (Year) - SXXEXX - Episode Title.ext`
* **Real-Time WebSockets**: Live, throttled progress bars and speeds updated on the dashboard using `Socket.IO`.
* **Google OAuth 2.0**: Secure authentication with domain validation and profile picture display.
* **Multi-Role Administration**: Assign roles (Admin, Moderator, User, or Pending Approval) and manage active user accounts and server-wide downloads directly from the frontend.

---

## 🛠️ Technology Stack

* **Backend**: Python 3.8+ (Flask, Flask-SocketIO, Flask-CORS, requests, python-dotenv, integration SDKs)
* **Frontend**: Vanilla HTML5, CSS3, and ES6 JavaScript (Single Page Application, no build step required)
* **Database**: SQLite3 (automatically initialized and migrated using `schema.sql`)
* **Real-time updates**: Gevent / WebSockets

---

## 📂 Project Structure

```
P121 - RICO.CX v4/
├── backend/
│   ├── models/            # Database representation models (User, Group, Result)
│   ├── routes/            # Flask blueprint API routes (api.py)
│   ├── services/          # Third-party integration clients
│   ├── utils/             # Helper utilities
│   ├── app.py             # Flask application setup & socketio initialization
│   └── database.py        # SQLite class wrapper with auto-migrations
├── frontend/              # Web client files (SPA)
│   ├── fonts/             # Custom interface typography
│   ├── index.html         # Application viewport index
│   ├── index.css          # Application layout stylesheets
│   ├── main.js            # Core webapp controller & API connection layer
│   └── socket.io.esm.min.js
├── tests/                 # Integration and unit tests
├── main.py                # Server entry point
├── schema.sql             # Relational SQL database schema
├── requirements.txt       # Python package dependencies
└── LICENSE                # MIT License
```

---

## ⚙️ Configuration & Environment Variables

Create a `.env` file in the root directory to configure the application:

| Variable | Description | Default |
|:---|:---|:---|
| `PORT` | The port the Flask web application runs on. | `5000` |
| `DEBUG_MODE` | Whether to run Flask in debug mode (`True`/`False`). | `True` |
| `USE_SSL` | Enable ad-hoc SSL encryption for local Google OAuth callbacks (`True`/`False`). | `True` |
| `DATABASE_PATH` | File path to the SQLite database. | `ricocx.db` |
| `FLASK_SECRET_KEY` | Secret key for Flask sessions. | `rico_cx_secret_key_129837` |
| `PROWLARR_URL` | Base URL of your Prowlarr instance. | `http://localhost:9696` |
| `PROWLARR_API_KEY` | API Key for your Prowlarr instance. | *None* |
| `TORBOX_API_KEY` | API Key for the debrid client. | *None* |
| `TMDB_API_KEY` | API Key for The Movie Database. | *None* |
| `ROOT_LIBRARY_LOCATION` | Local path where finished files will be moved. | `./library` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID. | *None* |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret. | *None* |

---

## 🚀 Installation & Running

### Prerequisites
* Python 3.8+
* A running **Prowlarr** instance
* A premium account API key for the debrid integration
* **TMDb** API key
* **Google Cloud Console** OAuth Client Credentials

### Step-by-Step Setup

1. **Clone the repository** and navigate to the project directory:
   ```bash
   cd "P121 - RICO.CX v4"
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. **Install the dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup your environment variables**:
   Create a `.env` file in the project root and fill in your keys (see [Configuration](#-configuration--environment-variables) above).

5. **Start the server**:
   ```bash
   python main.py
   ```

6. **Open the web dashboard**:
   Navigate to `https://localhost:5000` (or `http://localhost:5000` if `USE_SSL=False`) in your web browser.

> [!NOTE]
> Google OAuth requires HTTPS callbacks for local development unless using localhost. Enabling `USE_SSL=True` runs the server with ad-hoc SSL certificates (`https://`), allowing easy Google OAuth authentication locally.

---

## 🔒 Authentication & Admin Bootstrapping

RICO.CX implements a multi-tier group authorization system:

* **Admin**: Complete access to configuration settings, user management, and global server downloads.
* **Moderator**: Access to server-wide downloads list and user roles (read-only list).
* **User**: Access to search and download, and viewing their own downloads.
* **Pending Approval**: Newly registered users who are awaiting admin review.

### First Boot Setup (Seeding the Admin)
1. When you run the application with an empty database, the system starts with zero registered users.
2. The **very first user** to log in using the Google OAuth button will bypass the approval check and be automatically assigned the **Admin** role.
3. All subsequent users who log in will be set to **None (Pending Approval)** and will see an approval pending message.
4. The Admin can log in, click **Admin Panel**, and navigate to the **Users** tab to approve pending accounts and assign them roles.

---

## 🎬 Media Library Curation Layout

Downloads are automatically sorted, renamed, and mirrored from remote cloud storage to your local `ROOT_LIBRARY_LOCATION` directory.

### Example Directory Tree
```
library/
├── MOVIES/
│   └── Inception (2010) {tmdb-27205}/
│       └── Inception (2010) {tmdb-27205}.mkv
└── TV SHOWS/
    └── Breaking Bad (2008) {tmdb-1396}/
        └── Season 01/
            ├── Breaking Bad (2008) - S01E01 - Pilot.mkv
            ├── Breaking Bad (2008) - S01E02 - Cat's in the Bag....mkv
            └── Breaking Bad (2008) - S01E03 - ...And the Bag's in the River.mkv
```

---

## 🧪 Running Tests

The test suite runs integration and unit tests using Python's `unittest` framework. To run tests, execute:
```bash
python -m unittest discover tests
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
