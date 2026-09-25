"""Tests for SearchClient season-pack dual-query expansion helpers."""
import unittest

from backend.services.search_client import _build_season_query_variants, _deduplicate_torrent_results
from backend.models.result import TorrentResult


def _make_torrent(title="Test", size=1000, url="magnet:?xt=urn:btih:abc", guid="guid1", info_hash="abc"):
	return TorrentResult(
		title=title,
		size=size,
		download_url=url,
		seeders=10,
		leechers=2,
		indexer="TestIndexer",
		guid=guid,
		info_hash=info_hash
	)


class TestBuildSeasonQueryVariants(unittest.TestCase):
	"""Tests for _build_season_query_variants()."""

	# ── Season shorthand SXX ──────────────────────────────────────────────────

	def test_s_notation_generates_season_variant(self):
		variants = _build_season_query_variants("South Park S19")
		self.assertEqual(len(variants), 2)
		self.assertIn("south park s19", variants)
		self.assertIn("south park season 19", variants)

	def test_s_notation_with_zero_pad(self):
		variants = _build_season_query_variants("Breaking Bad S01")
		self.assertIn("breaking bad s01", variants)
		self.assertIn("breaking bad season 1", variants)

	def test_s_notation_single_digit(self):
		variants = _build_season_query_variants("The Office S3")
		self.assertIn("the office s3", variants)
		self.assertIn("the office season 3", variants)

	# ── Season longhand "Season XX" ───────────────────────────────────────────

	def test_season_word_generates_s_variant(self):
		variants = _build_season_query_variants("South Park Season 19")
		self.assertEqual(len(variants), 2)
		self.assertIn("south park season 19", variants)
		self.assertIn("south park s19", variants)

	def test_season_word_pads_number(self):
		variants = _build_season_query_variants("Breaking Bad Season 1")
		self.assertIn("breaking bad s01", variants)

	def test_season_word_double_digit(self):
		variants = _build_season_query_variants("Grey's Anatomy Season 15")
		self.assertIn("grey's anatomy s15", variants)

	# ── Episode queries — must NOT expand ────────────────────────────────────

	def test_episode_query_not_expanded(self):
		variants = _build_season_query_variants("South Park S19E07")
		self.assertEqual(len(variants), 1)
		self.assertEqual(variants[0], "south park s19e07")

	def test_episode_query_lowercase_not_expanded(self):
		variants = _build_season_query_variants("south park s19e07")
		self.assertEqual(len(variants), 1)

	# ── Plain title queries — must NOT expand ────────────────────────────────

	def test_plain_title_not_expanded(self):
		variants = _build_season_query_variants("Breaking Bad")
		self.assertEqual(len(variants), 1)
		self.assertEqual(variants[0], "breaking bad")

	def test_plain_movie_not_expanded(self):
		variants = _build_season_query_variants("Inception 2010")
		self.assertEqual(len(variants), 1)

	# ── Input normalisation ───────────────────────────────────────────────────

	def test_input_already_lowercase_s(self):
		variants = _build_season_query_variants("south park s19")
		self.assertIn("south park s19", variants)
		self.assertIn("south park season 19", variants)

	def test_input_already_lowercase_season(self):
		variants = _build_season_query_variants("south park season 19")
		self.assertIn("south park s19", variants)

	def test_extra_whitespace_stripped(self):
		variants = _build_season_query_variants("  South Park S19  ")
		self.assertIn("south park season 19", variants)


class TestDeduplicateTorrentResults(unittest.TestCase):
	"""Tests for _deduplicate_torrent_results()."""

	def test_empty_list(self):
		self.assertEqual(_deduplicate_torrent_results([]), [])

	def test_no_duplicates_unchanged(self):
		results = [
			_make_torrent(title="Show.S01.1080p", url="magnet:abc", guid="g1", info_hash="h1"),
			_make_torrent(title="Show.S01.720p",  url="magnet:def", guid="g2", info_hash="h2"),
		]
		deduped = _deduplicate_torrent_results(results)
		self.assertEqual(len(deduped), 2)

	def test_dedupe_by_url(self):
		r1 = _make_torrent(url="magnet:abc", guid="g1", info_hash="h1")
		r2 = _make_torrent(url="magnet:abc", guid="g2", info_hash="h2")  # same URL
		deduped = _deduplicate_torrent_results([r1, r2])
		self.assertEqual(len(deduped), 1)

	def test_dedupe_by_guid(self):
		r1 = _make_torrent(url="magnet:aaa", guid="same-guid", info_hash="h1")
		r2 = _make_torrent(url="magnet:bbb", guid="same-guid", info_hash="h2")
		deduped = _deduplicate_torrent_results([r1, r2])
		self.assertEqual(len(deduped), 1)

	def test_dedupe_by_info_hash(self):
		r1 = _make_torrent(url="magnet:aaa", guid="g1", info_hash="SAMEHASH")
		r2 = _make_torrent(url="magnet:bbb", guid="g2", info_hash="samehash")  # case insensitive
		deduped = _deduplicate_torrent_results([r1, r2])
		self.assertEqual(len(deduped), 1)

	def test_dedupe_by_title_size(self):
		r1 = _make_torrent(title="Same Release", size=5000, url="", guid="", info_hash="")
		r2 = _make_torrent(title="Same Release", size=5000, url="", guid="", info_hash="")
		deduped = _deduplicate_torrent_results([r1, r2])
		self.assertEqual(len(deduped), 1)

	def test_preserves_first_occurrence(self):
		r1 = _make_torrent(title="First",  url="magnet:abc", guid="g1", info_hash="h1")
		r2 = _make_torrent(title="Second", url="magnet:abc", guid="g2", info_hash="h2")
		deduped = _deduplicate_torrent_results([r1, r2])
		self.assertEqual(deduped[0].title, "First")

	def test_unique_results_from_both_variants(self):
		"""Simulates merging SXX and 'Season XX' results with one overlap."""
		r_s   = _make_torrent(title="Show.S01.1080p", url="magnet:aaa", guid="g1", info_hash="h1")
		r_sea = _make_torrent(title="Show.Season.1.1080p", url="magnet:bbb", guid="g2", info_hash="h2")
		r_dup = _make_torrent(title="Show.S01.1080p", url="magnet:aaa", guid="g3", info_hash="h3")  # duplicate URL
		deduped = _deduplicate_torrent_results([r_s, r_sea, r_dup])
		self.assertEqual(len(deduped), 2)


if __name__ == "__main__":
	unittest.main()
