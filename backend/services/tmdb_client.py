import os
import re
import requests
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

class TmdbClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("TMDB_API_KEY", "")
        self.base_url = "https://api.themoviedb.org/3"

    def search_movie(self, query: str, year: int = None) -> Optional[dict]:
        """Searches for a movie on TMDB and returns title, year, and TMDB ID."""
        if not self.api_key:
            logger.warning("TMDB API Key not configured. Skipping movie search.")
            return None
            
        url = f"{self.base_url}/search/movie"
        params = {
            "api_key": self.api_key,
            "query": query
        }
        if year:
            params["year"] = int(year)
            
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            results = resp.json().get("results", [])

            # Fallback if year constraint returns 0 results
            if not results and year:
                params.pop("year", None)
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                results = resp.json().get("results", [])

            if results:
                query_clean = re.sub(r'[^\w\s]', '', query.lower()).strip()

                def score_candidate(r):
                    name_raw = r.get("title", "") or r.get("name", "")
                    name_lower = name_raw.lower()
                    name_clean = re.sub(r'[^\w\s]', '', name_lower).strip()

                    if name_clean == query_clean:
                        return 100
                    if name_clean.rstrip('s') == query_clean.rstrip('s'):
                        return 90
                    if re.search(r'\b' + re.escape(query_clean) + r's?\s*[:\-]', name_raw, re.IGNORECASE):
                        return 80
                    if re.search(r'\b' + re.escape(query_clean) + r's?\b', name_lower):
                        return 50
                    return 0

                best_match = results[0]
                best_score = -1
                for r in results:
                    s = score_candidate(r)
                    if s > best_score:
                        best_score = s
                        best_match = r

                match = best_match

                release_date = match.get("release_date", "")
                match_year = release_date.split("-")[0] if release_date else ""
                poster_path = match.get("poster_path")
                poster_url = f"https://image.tmdb.org/t/p/w185{poster_path}" if poster_path else None
                return {
                    "title": match.get("title"),
                    "year": match_year,
                    "id": match.get("id"),
                    "poster_url": poster_url
                }
        except Exception as e:
            logger.error(f"TMDB search_movie failed: {e}")
        return None

    def search_tv(self, query: str, year: int = None) -> Optional[dict]:
        """Searches for a TV show on TMDB and returns title, first air year, and TMDB ID."""
        if not self.api_key:
            logger.warning("TMDB API Key not configured. Skipping TV search.")
            return None
            
        url = f"{self.base_url}/search/tv"
        params = {
            "api_key": self.api_key,
            "query": query
        }
        if year:
            params["first_air_date_year"] = int(year)
            
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            results = resp.json().get("results", [])

            # Fallback if year constraint returns 0 results
            if not results and year:
                params.pop("first_air_date_year", None)
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                results = resp.json().get("results", [])

            if results:
                query_clean = re.sub(r'[^\w\s]', '', query.lower()).strip()

                def score_candidate(r):
                    name_raw = r.get("name", "") or r.get("title", "")
                    name_lower = name_raw.lower()
                    name_clean = re.sub(r'[^\w\s]', '', name_lower).strip()

                    if name_clean == query_clean:
                        return 100
                    if name_clean.rstrip('s') == query_clean.rstrip('s'):
                        return 90
                    if re.search(r'\b' + re.escape(query_clean) + r's?\s*[:\-]', name_raw, re.IGNORECASE):
                        return 80
                    if re.search(r'\b' + re.escape(query_clean) + r's?\b', name_lower):
                        return 50
                    return 0

                best_match = results[0]
                best_score = -1
                for r in results:
                    s = score_candidate(r)
                    if s > best_score:
                        best_score = s
                        best_match = r

                match = best_match

                first_air = match.get("first_air_date", "")
                match_year = first_air.split("-")[0] if first_air else ""
                poster_path = match.get("poster_path")
                poster_url = f"https://image.tmdb.org/t/p/w185{poster_path}" if poster_path else None
                return {
                    "title": match.get("name"),
                    "year": match_year,
                    "id": match.get("id"),
                    "poster_url": poster_url
                }
        except Exception as e:
            logger.error(f"TMDB search_tv failed: {e}")
        return None

    def get_tv_seasons(self, tv_id: int) -> List[int]:
        """Returns a sorted list of valid season numbers for a given TV show ID on TMDB."""
        if not self.api_key or not tv_id:
            return []
        url = f"{self.base_url}/tv/{tv_id}"
        params = {"api_key": self.api_key}
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            seasons = [s.get("season_number") for s in data.get("seasons", []) if s.get("season_number") is not None and s.get("season_number") > 0]
            return sorted(seasons)
        except Exception as e:
            logger.error(f"TMDB get_tv_seasons failed for ID {tv_id}: {e}")
            return []

    def get_episode_name(self, tv_id: int, season: int, episode: int) -> Optional[str]:
        """Gets the title of a specific episode from TMDB."""
        if not self.api_key:
            return None
        url = f"{self.base_url}/tv/{tv_id}/season/{season}/episode/{episode}"
        params = {
            "api_key": self.api_key
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("name")
        except Exception as e:
            logger.error(f"TMDB get_episode_name failed for TV ID {tv_id} S{season}E{episode}: {e}")
        return None
