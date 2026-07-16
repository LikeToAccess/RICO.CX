import os
import requests
import logging
from typing import List
from ..models.result import TorrentResult, AggregatedResult
from .search_cache import global_search_cache

logger = logging.getLogger(__name__)

class SearchClient:
    def __init__(self, base_url: str = None, api_key: str = None):
        # Allow passing config directly, or fall back to env vars
        self.base_url = (base_url or os.environ.get("PROWLARR_URL", "http://localhost:9696")).rstrip("/")
        self.api_key = api_key or os.environ.get("PROWLARR_API_KEY", "")

    def search(self, query: str, category: str = None) -> List[AggregatedResult]:
        """
        Searches Prowlarr indexers for the given query and category.
        Returns a list of AggregatedResult objects, where torrents for the
        same movie/show are grouped. Uses an in-memory cache for speed.
        """
        if not query or not query.strip():
            return []

        # 1. Check exact query cache hit
        cached_results = global_search_cache.get_by_query(query, category)
        if cached_results is not None:
            logger.info(f"Search cache HIT (exact) for query: '{query}' (category: {category})")
            return cached_results

        # 2. Check matching cards cache hit (sub-query/fuzzy matching)
        matching_cards = global_search_cache.get_by_matching_cards(query, category)
        if matching_cards:
            logger.info(f"Search cache HIT (matching cards) for query: '{query}' (category: {category}) - Found {len(matching_cards)} cards.")
            return matching_cards

        if not self.api_key:
            logger.warning("SearchClient: Prowlarr API Key is not configured. Returning empty list.")
            return []

        url = f"{self.base_url}/api/v1/search"
        headers = {
            "X-Api-Key": self.api_key,
            "Accept": "application/json"
        }
        params = {
            "query": query
        }
        
        # Prowlarr categories: Movies = 2000, TV = 5000
        if category == "movie":
            params["categories"] = "2000"
        elif category == "tv":
            params["categories"] = "5000"
        else:
            params["categories"] = ["2000", "5000"]

        try:
            logger.info(f"Searching Prowlarr for query: '{query}' (category: {category})")
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            results_data = resp.json()
            
            # Convert raw results to TorrentResult models
            torrent_results = []
            for item in results_data:
                torrent_results.append(TorrentResult.from_prowlarr(item))
                
            logger.info(f"Prowlarr returned {len(torrent_results)} raw torrent results.")
            
            # Aggregate the results by title, year, and category
            aggregated = AggregatedResult.aggregate(torrent_results)
            logger.info(f"Aggregated into {len(aggregated)} media cards.")
            
            # Cache the query and the individual cards
            global_search_cache.set(query, category, aggregated)
            
            return aggregated
        except Exception as e:
            logger.error(f"SearchClient: Prowlarr search failed: {e}")
            return []
