import logging
import os
import re
from typing import Any, Dict, List, Optional, Union
import requests

logger = logging.getLogger(__name__)


class TmdbClient:
	"""
	Client for fetching movie and TV show metadata from The Movie Database (TMDb) API.
	"""
	def __init__(self, api_key: Optional[str] = None) -> None:
		self.api_key = api_key or os.environ.get("TMDB_API_KEY", "")
		self.base_url = "https://api.themoviedb.org/3"

	def search_movie(self, query: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
		"""Searches for a movie on TMDB and returns title, year, poster URL, and TMDB ID."""
		if not self.api_key:
			logger.warning("TMDB API Key not configured. Skipping movie search.")
			return None

		url = f"{self.base_url}/search/movie"
		params: Dict[str, Union[str, int]] = {
			"api_key": self.api_key,
			"query": query
		}
		if year is not None:
			params["year"] = int(year)

		try:
			resp = requests.get(url, params=params, timeout=10)
			resp.raise_for_status()
			results = resp.json().get("results", [])

			if not results and year is not None:
				params.pop("year", None)
				resp = requests.get(url, params=params, timeout=10)
				resp.raise_for_status()
				results = resp.json().get("results", [])

			if results:
				query_clean = re.sub(r'[^\w\s]', '', query.lower()).strip()

				def score_candidate(r: Dict[str, Any]) -> int:
					name_raw = str(r.get("title", "") or r.get("name", ""))
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
				for candidate in results:
					if isinstance(candidate, dict):
						s = score_candidate(candidate)
						if s > best_score:
							best_score = s
							best_match = candidate

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
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("TMDB search_movie failed: %s", exc)
		return None

	def search_tv(self, query: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
		"""Searches for a TV show on TMDB and returns title, first air year, poster URL, and TMDB ID."""
		if not self.api_key:
			logger.warning("TMDB API Key not configured. Skipping TV search.")
			return None

		url = f"{self.base_url}/search/tv"
		params: Dict[str, Union[str, int]] = {
			"api_key": self.api_key,
			"query": query
		}
		if year is not None:
			params["first_air_date_year"] = int(year)

		try:
			resp = requests.get(url, params=params, timeout=10)
			resp.raise_for_status()
			results = resp.json().get("results", [])

			if not results and year is not None:
				params.pop("first_air_date_year", None)
				resp = requests.get(url, params=params, timeout=10)
				resp.raise_for_status()
				results = resp.json().get("results", [])

			if results:
				query_clean = re.sub(r'[^\w\s]', '', query.lower()).strip()

				def score_candidate(r: Dict[str, Any]) -> int:
					name_raw = str(r.get("name", "") or r.get("title", ""))
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
				for candidate in results:
					if isinstance(candidate, dict):
						s = score_candidate(candidate)
						if s > best_score:
							best_score = s
							best_match = candidate

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
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("TMDB search_tv failed: %s", exc)
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
			seasons: List[int] = []
			for s in data.get("seasons", []):
				if isinstance(s, dict):
					s_num = s.get("season_number")
					if isinstance(s_num, int) and s_num > 0:
						seasons.append(s_num)
			return sorted(seasons)
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("TMDB get_tv_seasons failed for ID %s: %s", tv_id, exc)
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
			name = resp.json().get("name")
			return str(name) if name is not None else None
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("TMDB get_episode_name failed for TV ID %s S%dE%d: %s", tv_id, season, episode, exc)
		return None
