# Server

This directory contains the backend Flask application and all server-side components for RICO.CX - a video streaming and download service.

## Application Overview

RICO.CX is a Flask-based web application that provides video search, streaming, and download functionality with Google OAuth authentication, user management, and Real-Debrid integration.

## API Routes

### Public Routes
- **`GET /`** - Home page (supports optional video URL parameter)
- **`GET /<video_url>`** - Home page with specific video URL
- **`GET /search`** - Search results page
- **`GET /search/<query>`** - Search results page with query
- **`GET /login`** - Google OAuth login initiation
- **`GET /login/callback`** - Google OAuth callback handler
- **`GET /static/js/settings.js`** - Dynamic settings JavaScript (templated)

### Protected Routes (Login Required)
- **`GET /admin`** - Admin panel (admin/root only)
- **`POST /admin`** - Admin actions (delete, ban, unban, change_role)
- **`GET /logs`** - Live log viewing (admin/root only)
- **`GET /pending`** - Pending approval page
- **`GET /banned`** - Banned user page
- **`GET /logout`** - User logout

### API Endpoints
- **`GET /api/v2/search?q=<query>`** - Search for movies/videos
- **`GET /api/v2/getvideo?page_url=<url>`** - Get video URL and metadata
- **`GET /api/v2/popular`** - Get popular content
- **`POST /api/v2/download`** - Download video from page URL
- **`GET /test/<filename>`** - Test download status

## Core Components

### Authentication & Authorization
- **Google OAuth 2.0** integration for user authentication
- **Role-based access control** (Root, Administrators, Members)
- **User management** with ban/unban functionality
- **Group membership** system for access control

### Video Processing
- **Web scraping** for video content discovery
- **Video URL extraction** and metadata parsing
- **Real-Debrid integration** for premium downloads
- **Caching system** with TTL and LFU caches for performance

### File Structure

#### Core Application Files
- **`app.py`** - Main Flask application with all routes and business logic
- **`scraper.py`** - Web scraping functionality for video content
- **`scraper_tools.py`** - Scraping utility functions and helpers
- **`download.py`** - Download handling and file management
- **`download_engine.py`** - Download engine implementation with queue management
- **`realdebrid.py`** - Real-Debrid API integration for premium downloads
- **`settings.py`** - Application configuration and environment variables

#### User & Database Management
- **`user.py`** - User model and authentication logic
- **`group.py`** - Group membership and role management
- **`database.py`** - Database operations and initialization
- **`schema.sql`** - SQLite database schema definition

#### Utilities & Support
- **`bot.py`** - Bot functionality and automation
- **`result.py`** - Search result handling and formatting
- **`timer.py`** - Performance timing utilities
- **`element_find.py`** - Selenium web element finding utilities
- **`element_wait_until.py`** - Selenium wait condition utilities
- **`test.py`** - Test utilities and helpers
- **`waitress_serve.py`** - Production WSGI server configuration

#### Configuration & Data
- **`requirements.txt`** - Python dependencies
- **`country_codes.json`** - Country code mappings for localization
- **`run.cmd`** - Windows startup script

#### Frontend Assets
- **`static/`** - Static web assets organized by type
  - **`css/`** - Stylesheets (main styles, animations, video player, etc.)
  - **`js/`** - JavaScript files (search, download, video player functionality)
  - **`img/`** - Images and icons
  - **`fonts/`** - Custom fonts (Poppins, YouTube Sans, etc.)
  - **`video/`** - Video assets (loading animations)
  - **`webfonts/`** - Web font files

- **`templates/`** - Jinja2 HTML templates for server-side rendering
  - **`pages/`** - Main page templates (home, search, admin, etc.)
  - **`layouts/`** - Base layout templates
  - **`includes/`** - Reusable template components

#### Extensions & Testing
- **`chrome_extensions/`** - Browser extension files (uBlock Origin)
- **`tests/`** - Unit tests for application components
- **`test_files/`** - Test data and sample files

## Key Features

### Caching System
- **Search Cache**: TTL cache (24 hours) for search results
- **Video URL Cache**: TTL cache (1 hour 55 minutes) for video URLs
- **Video Data Cache**: LFU cache for video metadata

### Error Handling
Comprehensive error code system with descriptive messages:
- **APPLE**: Failed to download video
- **AVATAR**: Failed to get video URL
- **ASTRO**: Failed to get video data
- **BANANA**: No result provided for download
- **FALCON**: Failed to communicate with search service
- **GUITAR**: Invalid Real-Debrid API key
- **HAMMER**: Infringing video download blocked

### Security Features
- **OAuth 2.0** authentication with Google
- **Role-based access control**
- **Input validation** and sanitization
- **Secure session management**

## Running the Server

```bash
cd server
pip install -r requirements.txt
python app.py
```

Or on Windows:
```cmd
run.cmd
```
