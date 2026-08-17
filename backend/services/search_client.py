import logging
import os
from typing import Dict, List, Optional, Union
import requests
from ..models.result import AggregatedResult, TorrentResult
from .search_cache import global_search_cache

logger = logging.getLogger(__name__)


class SearchClient:
	"""
	Client for querying Prowlarr indexers and aggregating torrent search results.
	"""
	def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None) -> None:
		raw_url = base_url or os.environ.get("PROWLARR_URL") or "http://localhost:9696"
		self.base_url = raw_url.rstrip("/")
		self.api_key = api_key or os.environ.get("PROWLARR_API_KEY", "")

	def search(self, query: str, category: Optional[str] = None) -> List[AggregatedResult]:
		"""
		Searches Prowlarr indexers for the given query and category.
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

		url = f"{self.base_url}/api/v1/search"
		headers = {
			"X-Api-Key": self.api_key,
			"Accept": "application/json"
		}
		params: Dict[str, Union[str, List[str]]] = {
			"query": query
		}

		if category == "movie":
			params["categories"] = "2000"
		elif category == "tv":
			params["categories"] = "5000"
		else:
			params["categories"] = ["2000", "5000"]

		try:
			logger.info("Searching Prowlarr for query: '%s' (category: %s)", query, category)
			resp = requests.get(url, headers=headers, params=params, timeout=30)
			resp.raise_for_status()
			results_data = resp.json()

			torrent_results: List[TorrentResult] = []
			if isinstance(results_data, list):
				for item in results_data:
					if isinstance(item, dict):
						torrent_results.append(TorrentResult.from_prowlarr(item))

			logger.info("Prowlarr returned %d raw torrent results.", len(torrent_results))

			aggregated = AggregatedResult.aggregate(torrent_results)
			logger.info("Aggregated into %d media cards.", len(aggregated))

			global_search_cache.set(query, category, aggregated)

			return aggregated
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("SearchClient: Prowlarr search failed: %s", exc)
			return []
