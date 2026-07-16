# RICO.CX v3

A modern, fast, and maintainable media search and download management system.

## Technologies
- **Frontend:** React (Vite, TypeScript), Framer Motion, Axios, React Icons
- **Backend:** Flask, SQLite
- **Services:** Real-Debrid (Downloads), Milkie.cc (Search), FileBot (Media Identification)

## Features
- Universal search bar: Supports generic search strings, torrent hashes, and magnet links.
- Direct Real-Debrid integration: Magnet links and hashes bypass search and go straight to download.
- Modern UI: Smooth animations with Framer Motion and a clean dark aesthetic.
- Object-Oriented Design: Abstraction for search results, users, and services.

## Setup

### Backend
1. Install Python 3.10+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env` and fill in your API keys:
   ```bash
   RD_API_KEY=your_key
   MILKIE_API_KEY=your_key
   ```

### Frontend
1. Install Node.js
2. Navigate to `frontend/`:
   ```bash
   cd frontend
   npm install
   ```
3. Build the frontend (optional, for production):
   ```bash
   npm run build
   ```

## Running the Project

### Development
1. Start the backend:
   ```bash
   python main.py
   ```
2. Start the frontend (in another terminal):
   ```bash
   cd frontend
   npm run dev
   ```

### Production
The Flask app is configured to serve the `frontend/dist` directory.
1. Build the frontend: `cd frontend && npm run build`
2. Run the backend: `python main.py`
3. Access at `http://localhost:5000`

## Structure
- `backend/`: Flask application, routes, and logic.
  - `models/`: Domain models (User, Result).
  - `services/`: External API integrations (RealDebrid, Milkie, FileBot).
  - `routes/`: API endpoints.
- `frontend/`: React application.
  - `src/App.tsx`: Main UI logic and animations.
