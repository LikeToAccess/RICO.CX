import time
import re
import threading
from typing import List, Dict, Tuple, Optional
from ..models.result import AggregatedResult

class SearchCache:
    def __init__(self, ttl_seconds: int = 600):
        self.ttl = ttl_seconds
        self.lock = threading.Lock()
        # maps (query_string, category) -> (List[AggregatedResult], expiry_time)
        self._query_cache: Dict[Tuple[str, Optional[str]], Tuple[List[AggregatedResult], float]] = {}
        # maps (clean_title_lower, year, is_tv) -> (AggregatedResult, expiry_time)
        self._cards_cache: Dict[Tuple[str, Optional[int], bool], Tuple[AggregatedResult, float]] = {}

    def _clean_expired_under_lock(self):
        now = time.time()
        self._query_cache = {k: v for k, v in self._query_cache.items() if v[1] > now}
        self._cards_cache = {k: v for k, v in self._cards_cache.items() if v[1] > now}

    def get_by_query(self, query: str, category: Optional[str]) -> Optional[List[AggregatedResult]]:
        with self.lock:
            self._clean_expired_under_lock()
            key = (query.lower().strip(), category)
            if key in self._query_cache:
                return self._query_cache[key][0]
            return None

    def get_by_matching_cards(self, query: str, category: Optional[str]) -> List[AggregatedResult]:
        with self.lock:
            self._clean_expired_under_lock()
            q_words = re.sub(r'[\.\-\_\+\[\]\(\)\:\,]', ' ', query.lower()).split()
            if not q_words:
                return []
            
            matches = []
            for (title_lower, year, is_tv), (card, expiry) in list(self._cards_cache.items()):
                # Filter by category if specified
                if category == "movie" and is_tv:
                    continue
                if category == "tv" and not is_tv:
                    continue
                
                # Check keyword containment
                t_words = re.sub(r'[\.\-\_\+\[\]\(\)\:\,]', ' ', title_lower).split()
                if all(any(qw in tw for tw in t_words) for qw in q_words):
                    matches.append(card)
                    
            # Sort matches by sum of seeders descending
            matches.sort(key=lambda x: sum(d.seeders for d in x.downloads), reverse=True)
            return matches

    def set(self, query: str, category: Optional[str], results: List[AggregatedResult]):
        with self.lock:
            self._clean_expired_under_lock()
            now = time.time()
            expiry = now + self.ttl
            
            # Save query
            query_key = (query.lower().strip(), category)
            self._query_cache[query_key] = (results, expiry)
            
            # Save individual cards
            for card in results:
                card_key = (card.clean_title.lower(), card.year, card.is_tv)
                self._cards_cache[card_key] = (card, expiry)

# Global singleton cache instance (default TTL: 10 minutes)
global_search_cache = SearchCache(ttl_seconds=600)
