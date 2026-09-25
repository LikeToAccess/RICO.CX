"""Client for fetching movie and TV show metadata from The Movie Database (TMDb) API."""
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple, Union
import requests

logger = logging.getLogger(__name__)

# Persistent thread-safe cache for TMDb lookups (TTL: 24 hours)
_TMDB_CACHE_LOCK = threading.Lock()
_TMDB_CACHE: Dict[Tuple[str, str, Optional[int]], Tuple[Optional[Dict[str, Any]], float]] = {}
_TMDB_CACHE_TTL = 86400.0  # 24 hours in seconds


def clear_tmdb_cache() -> None:
	"""Clears the TMDb in-memory cache (used for testing)."""
	with _TMDB_CACHE_LOCK:
		_TMDB_CACHE.clear()


TMDB_GENRES: Dict[int, str] = {
	28: "Action",
	12: "Adventure",
	16: "Animation",
	35: "Comedy",
	80: "Crime",
	99: "Documentary",
	18: "Drama",
	10751: "Family",
	14: "Fantasy",
	36: "History",
	27: "Horror",
	10402: "Music",
	9648: "Mystery",
	10749: "Romance",
	878: "Sci-Fi",
	10770: "TV Movie",
	53: "Thriller",
	10752: "War",
	37: "Western",
	10759: "Action & Adventure",
	10762: "Kids",
	10763: "News",
	10764: "Reality",
	10765: "Sci-Fi & Fantasy",
	10766: "Soap",
	10767: "Talk",
	10768: "War & Politics",
}


class TmdbClient:
	"""
	Client for fetching movie and TV show metadata from The Movie Database (TMDb) API.
	Includes persistent in-memory caching and parallel batch resolution.
	"""

	def __init__(self, api_key: Optional[str] = None) -> None:
		self.api_key = api_key or os.environ.get("TMDB_API_KEY", "")
		self.base_url = "https://api.themoviedb.org/3"

	def _get_from_cache(self, media_type: str, query: str, year: Optional[int]) -> Optional[Tuple[bool, Optional[Dict[str, Any]]]]:
		key = (media_type, query.lower().strip(), year)
		with _TMDB_CACHE_LOCK:
			if key in _TMDB_CACHE:
				data, expiry = _TMDB_CACHE[key]
				if time.time() < expiry:
					return (True, data)
				del _TMDB_CACHE[key]
		return None

	def _save_to_cache(self, media_type: str, query: str, year: Optional[int], data: Optional[Dict[str, Any]]) -> None:
		key = (media_type, query.lower().strip(), year)
		expiry = time.time() + _TMDB_CACHE_TTL
		with _TMDB_CACHE_LOCK:
			if len(_TMDB_CACHE) > 5000:
				now = time.time()
				expired = [k for k, v in _TMDB_CACHE.items() if v[1] <= now]
				for k in expired:
					del _TMDB_CACHE[k]
			_TMDB_CACHE[key] = (data, expiry)

	def search_movie(self, query: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
		"""Searches for a movie on TMDB and returns title, year, poster URL, and TMDB ID."""
		if not self.api_key or not query or not query.strip():
			return None

		cached = self._get_from_cache("movie", query, year)
		if cached is not None:
			return cached[1]

		url = f"{self.base_url}/search/movie"
		params: Dict[str, Union[str, int]] = {
			"api_key": self.api_key,
			"query": query
		}
		if year is not None:
			params["year"] = int(year)

		try:
			resp = requests.get(url, params=params, timeout=8)
			resp.raise_for_status()
			results = resp.json().get("results", [])

			if not results and year is not None:
				params.pop("year", None)
				resp = requests.get(url, params=params, timeout=8)
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
				result_data = {
					"title": match.get("title"),
					"year": match_year,
					"id": match.get("id"),
					"poster_url": poster_url
				}
				self._save_to_cache("movie", query, year, result_data)
				return result_data

			self._save_to_cache("movie", query, year, None)
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("TMDB search_movie failed: %s", exc)
		return None

	def search_tv(self, query: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
		"""Searches for a TV show on TMDB and returns title, first air year, poster URL, and TMDB ID."""
		if not self.api_key or not query or not query.strip():
			return None

		cached = self._get_from_cache("tv", query, year)
		if cached is not None:
			return cached[1]

		url = f"{self.base_url}/search/tv"
		params: Dict[str, Union[str, int]] = {
			"api_key": self.api_key,
			"query": query
		}
		if year is not None:
			params["first_air_date_year"] = int(year)

		try:
			resp = requests.get(url, params=params, timeout=8)
			resp.raise_for_status()
			results = resp.json().get("results", [])

			if not results and year is not None:
				params.pop("first_air_date_year", None)
				resp = requests.get(url, params=params, timeout=8)
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
				result_data = {
					"title": match.get("name"),
					"year": match_year,
					"id": match.get("id"),
					"poster_url": poster_url
				}
				self._save_to_cache("tv", query, year, result_data)
				return result_data

			self._save_to_cache("tv", query, year, None)
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("TMDB search_tv failed: %s", exc)
		return None

	def resolve_posters_batch(self, cards: List[Any]) -> None:
		"""
		Concurrently resolves TMDb posters in parallel across multiple cards using thread pool.
		Mutates card.poster_url in place.
		"""
		if not self.api_key or not cards:
			return

		cards_to_resolve = [c for c in cards if getattr(c, 'poster_url', None) is None]
		if not cards_to_resolve:
			return

		def _worker(card: Any) -> None:
			try:
				if getattr(card, 'is_tv', False):
					res = self.search_tv(card.clean_title, card.year)
				else:
					res = self.search_movie(card.clean_title, card.year)
				if res:
					card.poster_url = res.get("poster_url")
			except Exception as e:  # pylint: disable=broad-exception-caught
				logger.debug("Parallel TMDb resolution failed for %s: %s", getattr(card, 'clean_title', ''), e)

		# Use bounded concurrent worker pool for low latency resolution
		if len(cards_to_resolve) == 1:
			_worker(cards_to_resolve[0])
			return

		max_workers = min(len(cards_to_resolve), 8)
		try:
			from gevent.pool import Pool as GeventPool  # type: ignore[import-untyped]
			pool = GeventPool(max_workers)
			pool.map(_worker, cards_to_resolve)
		except (ImportError, Exception):
			try:
				with ThreadPoolExecutor(max_workers=max_workers) as executor:
					list(executor.map(_worker, cards_to_resolve))
			except Exception as exc:  # pylint: disable=broad-exception-caught
				logger.error("Batch TMDb resolution error: %s", exc)

	def get_tv_seasons(self, tv_id: int) -> List[int]:
		"""Returns a sorted list of valid season numbers for a given TV show ID on TMDB."""
		if not self.api_key or not tv_id:
			return []
		url = f"{self.base_url}/tv/{tv_id}"
		params = {"api_key": self.api_key}
		try:
			resp = requests.get(url, params=params, timeout=8)
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
			resp = requests.get(url, params=params, timeout=8)
			resp.raise_for_status()
			name = resp.json().get("name")
			return str(name) if name is not None else None
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("TMDB get_episode_name failed for TV ID %s S%dE%d: %s", tv_id, season, episode, exc)
		return None

	def get_trending(
		self,
		media_type: str = "movie",
		time_window: str = "day",
		page: int = 1
	) -> Optional[Dict[str, Any]]:
		"""
		Fetches daily or weekly trending movies or TV shows from TMDB.
		Results are cached in memory for fast repeat access.
		"""
		if not self.api_key:
			return None

		media_type = "tv" if media_type == "tv" else "movie"
		time_window = "week" if time_window == "week" else "day"
		page = max(1, page)

		cached = self._get_from_cache("trending", f"{media_type}:{time_window}", page)
		if cached is not None:
			return cached[1]

		url = f"{self.base_url}/trending/{media_type}/{time_window}"
		params: Dict[str, Union[str, int]] = {
			"api_key": self.api_key,
			"page": page
		}

		try:
			resp = requests.get(url, params=params, timeout=8)
			resp.raise_for_status()
			raw_data = resp.json()
			results: List[Dict[str, Any]] = []

			for item in raw_data.get("results", []):
				if not isinstance(item, dict):
					continue
				is_tv = media_type == "tv" or item.get("media_type") == "tv"
				raw_title = str(item.get("name" if is_tv else "title") or "")
				if not raw_title:
					continue

				date_str = str(item.get("first_air_date" if is_tv else "release_date") or "")
				year_val: Optional[int] = None
				if date_str:
					try:
						year_val = int(date_str.split("-")[0])
					except (ValueError, IndexError):
						year_val = None

				poster_path = item.get("poster_path")
				poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
				backdrop_path = item.get("backdrop_path")
				backdrop_url = f"https://image.tmdb.org/t/p/original{backdrop_path}" if backdrop_path else None

				genre_names = [TMDB_GENRES[gid] for gid in item.get("genre_ids", []) if gid in TMDB_GENRES]

				results.append({
					"id": item.get("id"),
					"title": raw_title,
					"clean_title": raw_title,
					"year": year_val,
					"is_tv": is_tv,
					"overview": item.get("overview") or "",
					"poster_url": poster_url,
					"backdrop_url": backdrop_url,
					"vote_average": round(float(item.get("vote_average", 0.0)), 1),
					"vote_count": item.get("vote_count", 0),
					"popularity": round(float(item.get("popularity", 0.0)), 1),
					"genres": genre_names
				})

			parsed = {
				"page": raw_data.get("page", 1),
				"total_pages": raw_data.get("total_pages", 1),
				"total_results": raw_data.get("total_results", len(results)),
				"results": results
			}
			self._save_to_cache("trending", f"{media_type}:{time_window}", page, parsed)
			return parsed
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("TMDB get_trending failed: %s", exc)
			return None
