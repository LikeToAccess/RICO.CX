"""Client for querying Prowlarr indexers and aggregating torrent search results."""
import concurrent.futures
import logging
import os
import re
from typing import Dict, List, Optional, Union
import requests
from ..models.result import AggregatedResult, TorrentResult
from .search_cache import global_search_cache
from .tmdb_client import TmdbClient

logger = logging.getLogger(__name__)


def _build_season_query_variants(query: str) -> List[str]:
	"""
	Detects season-pack queries and returns both the 'S##' and 'Season ##' variants
	so results from indexers using either naming convention are captured.

	Rules:
	  - Only triggers when the query ends with a season-only token (no episode).
	    e.g. "South Park S19" / "South Park Season 19" — but NOT "South Park S19E07".
	  - Returns [original_variant, alternate_variant] when a season token is found.
	  - Returns [original_query] unchanged for all other queries.

	Examples:
	  "South Park S19"       -> ["south park s19",       "south park season 19"]
	  "South Park Season 19" -> ["south park season 19", "south park s19"]
	  "South Park S19E07"    -> ["south park s19e07"]   (episode — no expansion)
	  "Breaking Bad"         -> ["breaking bad"]         (no season — no expansion)
	"""
	q_lower = query.lower().strip()

	# Match standalone "s##" at end of query — but NOT "s##e##" (that's an episode)
	s_match = re.search(r'\bs(\d{1,2})\s*$', q_lower)
	if s_match and not re.search(r'\bs\d{1,2}e\d{1,2}\b', q_lower):
		num = s_match.group(1).lstrip('0') or '0'
		base = q_lower[:s_match.start()].strip()
		alternate = f"{base} season {num}"
		return [q_lower, alternate]

	# Match "season ##" (with or without a leading word boundary)
	season_match = re.search(r'\bseason\s+(\d{1,2})\s*$', q_lower)
	if season_match:
		num = int(season_match.group(1))
		base = q_lower[:season_match.start()].strip()
		alternate = f"{base} s{str(num).zfill(2)}"
		return [q_lower, alternate]

	return [q_lower]


def _deduplicate_torrent_results(results: List[TorrentResult]) -> List[TorrentResult]:
	"""
	Remove duplicate TorrentResult entries from a merged multi-query result list.
	Deduplication priority: download_url > guid > info_hash > (title, size) pair.
	"""
	seen_urls: set = set()
	seen_guids: set = set()
	seen_hashes: set = set()
	seen_title_size: set = set()
	deduped: List[TorrentResult] = []

	for r in results:
		url = (r.download_url or "").strip()
		guid = (r.guid or "").strip()
		info_hash = (r.info_hash or "").strip().lower()
		title_size = (r.title.strip().lower(), r.size)

		if url and url in seen_urls:
			continue
		if guid and guid in seen_guids:
			continue
		if info_hash and info_hash in seen_hashes:
			continue
		if title_size in seen_title_size:
			continue

		if url:
			seen_urls.add(url)
		if guid:
			seen_guids.add(guid)
		if info_hash:
			seen_hashes.add(info_hash)
		seen_title_size.add(title_size)
		deduped.append(r)

	return deduped


class SearchClient:
	"""
	Client for querying Prowlarr indexers and aggregating torrent search results.
	"""

	def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, tmdb_api_key: Optional[str] = None) -> None:
		raw_url = base_url or os.environ.get("PROWLARR_URL") or "http://localhost:9696"
		self.base_url = raw_url.rstrip("/")
		self.api_key = api_key or os.environ.get("PROWLARR_API_KEY", "")
		self.tmdb_api_key = tmdb_api_key or os.environ.get("TMDB_API_KEY", "")

	def _prowlarr_fetch(self, query: str, category: Optional[str]) -> List[TorrentResult]:
		"""
		Executes a single Prowlarr search and returns raw TorrentResult objects.
		Raises on HTTP errors; returns [] on empty or non-list response.
		"""
		url = f"{self.base_url}/api/v1/search"
		headers = {
			"X-Api-Key": self.api_key,
			"Accept": "application/json"
		}
		# Lowercase to work around a 1337x indexer quirk where Title Case +
		# uppercase SxxExx (e.g. "South Park S19E07") returns 0 results.
		params: Dict[str, Union[str, List[str]]] = {
			"query": query.lower()
		}

		if category == "movie":
			params["categories"] = "2000"
		elif category == "tv":
			params["categories"] = "5000"
		else:
			params["categories"] = ["2000", "5000"]

		resp = requests.get(url, headers=headers, params=params, timeout=30)
		resp.raise_for_status()
		results_data = resp.json()

		torrent_results: List[TorrentResult] = []
		if isinstance(results_data, list):
			for item in results_data:
				if isinstance(item, dict):
					torrent_results.append(TorrentResult.from_prowlarr(item))
		return torrent_results

	def search(self, query: str, category: Optional[str] = None) -> List[AggregatedResult]:
		"""
		Searches Prowlarr indexers for the given query and category.

		For season-pack queries (e.g. "South Park S19" or "South Park Season 19"),
		automatically runs both the shorthand (SXX) and longhand (Season XX) variants
		concurrently and merges/deduplicates the results so releases from indexers using
		either naming convention are always captured.
		"""
		if not query or not query.strip():
			return []

		cached_results = global_search_cache.get_by_query(query, category)
		if cached_results is not None:
			logger.info("Search cache HIT (exact) for query: '%s' (category: %s)", query, category)
			return cached_results

		matching_cards = global_search_cache.get_by_matching_cards(query, category)
		if matching_cards:
			logger.info(
				"Search cache HIT (matching cards) for query: '%s' (category: %s) - Found %d cards.",
				query, category, len(matching_cards)
			)
			return matching_cards

		if not self.api_key:
			logger.warning("SearchClient: Prowlarr API Key is not configured. Returning empty list.")
			return []

		# Build query variants (season-pack dual-search expansion)
		variants = _build_season_query_variants(query)
		is_expanded = len(variants) > 1
		if is_expanded:
			logger.info(
				"Season-pack query detected — running dual search: %s",
				" + ".join(f"'{v}'" for v in variants)
			)

		try:
			all_torrent_results: List[TorrentResult] = []

			if is_expanded:
				# Run both variants concurrently to avoid doubling latency
				with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
					futures = {
						executor.submit(self._prowlarr_fetch, v, category): v
						for v in variants
					}
					for future in concurrent.futures.as_completed(futures):
						variant_query = futures[future]
						try:
							results = future.result()
							logger.info(
								"Prowlarr variant '%s' returned %d raw results.",
								variant_query, len(results)
							)
							all_torrent_results.extend(results)
						except Exception as exc:  # pylint: disable=broad-exception-caught
							logger.warning(
								"SearchClient: Prowlarr variant '%s' failed: %s",
								variant_query, exc
							)
			else:
				logger.info("Searching Prowlarr for query: '%s' (category: %s)", query, category)
				all_torrent_results = self._prowlarr_fetch(variants[0], category)

			if is_expanded:
				before = len(all_torrent_results)
				all_torrent_results = _deduplicate_torrent_results(all_torrent_results)
				logger.info(
					"Dual-search merge: %d raw results -> %d after deduplication.",
					before, len(all_torrent_results)
				)

			logger.info("Prowlarr returned %d raw torrent results (total).", len(all_torrent_results))

			aggregated = AggregatedResult.aggregate(all_torrent_results)
			logger.info("Aggregated into %d media cards.", len(aggregated))

			# Concurrently resolve TMDb posters before saving into cache so cache hits include posters
			if self.tmdb_api_key:
				tmdb = TmdbClient(api_key=self.tmdb_api_key)
				tmdb.resolve_posters_batch(aggregated)

			global_search_cache.set(query, category, aggregated)

			return aggregated
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("SearchClient: Prowlarr search failed: %s", exc)
			return []
