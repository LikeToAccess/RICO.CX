# Server

This directory contains the backend Flask application and all server-side components for RICO.CX.

## Structure

- **`app.py`** - Main Flask application entry point
- **`scraper.py`** - Web scraping functionality
- **`scraper_tools.py`** - Scraping utility functions
- **`download.py`** - Download handling
- **`download_engine.py`** - Download engine implementation
- **`realdebrid.py`** - Real-Debrid integration
- **`bot.py`** - Bot functionality
- **`database.py`** - Database operations
- **`user.py`** - User management
- **`group.py`** - Group management
- **`result.py`** - Result handling
- **`settings.py`** - Application settings
- **`timer.py`** - Timer utilities
- **`element_find.py`** - Web element finding utilities
- **`element_wait_until.py`** - Web element waiting utilities
- **`test.py`** - Test utilities
- **`waitress_serve.py`** - WSGI server configuration
- **`requirements.txt`** - Python dependencies
- **`schema.sql`** - Database schema
- **`country_codes.json`** - Country code mappings
- **`run.cmd`** - Windows run script
- **`static/`** - Static web assets (CSS, JS, images, fonts)
- **`templates/`** - Jinja2 templates for the web interface
- **`chrome_extensions/`** - Chrome extension files
- **`tests/`** - Unit tests
- **`test_files/`** - Test data files

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
