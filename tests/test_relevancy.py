import unittest
import json
import os
from backend.models.result import TorrentResult, AggregatedResult


class TestRelevancyScoring(unittest.TestCase):
	def test_4k_dv_atmos_beats_1080p_high_seeders(self):
		# 4K HEVC Atmos DV release with 80 seeders
		four_k = TorrentResult(
			title="Interstellar.2014.2160p.UHD.BluRay.DV.HDR10.Atmos.HEVC-FLUX",
			size=25 * 1024 * 1024 * 1024,  # 25 GB
			download_url="magnet:?xt=urn:btih:1111",
			seeders=80,
			leechers=10,
			indexer="1337x"
		)
		# 1080p x264 stereo release with 3000 seeders
		ten_eighty = TorrentResult(
			title="Interstellar.2014.1080p.BrRip.x264.YIFY",
			size=2 * 1024 * 1024 * 1024,  # 2 GB
			download_url="magnet:?xt=urn:btih:2222",
			seeders=3000,
			leechers=50,
			indexer="1337x"
		)

		self.assertGreater(four_k.relevancy_score, ten_eighty.relevancy_score)
		agg = AggregatedResult.aggregate([ten_eighty, four_k])
		self.assertEqual(len(agg), 1)
		# four_k should be ordered #1
		self.assertEqual(agg[0].downloads[0].title, four_k.title)

	def test_ai_penalty_drops_below_720p(self):
		ai_release = TorrentResult(
			title="Interstellar.2014.2160p.IMAX.DV.HDR10.Ai Enhanced.H265.DTS HD.5.1 RIFE.4.15 60fps-DirtyHippie",
			size=38 * 1024 * 1024 * 1024,  # 38 GB
			download_url="magnet:?xt=urn:btih:3333",
			seeders=50,
			leechers=5,
			indexer="1337x"
		)
		seven_twenty = TorrentResult(
			title="Interstellar.2014.720p.BrRip.x264.YIFY",
			size=1 * 1024 * 1024 * 1024,  # 1 GB
			download_url="magnet:?xt=urn:btih:4444",
			seeders=500,
			leechers=10,
			indexer="1337x"
		)

		self.assertTrue(ai_release.is_ai)
		self.assertFalse(seven_twenty.is_ai)
		self.assertGreater(seven_twenty.relevancy_score, ai_release.relevancy_score)

	def test_cam_telesync_disqualification(self):
		cam_release = TorrentResult(
			title="Dune.Part.Two.2024.1080p.HD TS.X264-EMIN3M[TGx]",
			size=4 * 1024 * 1024 * 1024,
			download_url="magnet:?xt=urn:btih:5555",
			seeders=2500,
			leechers=100,
			indexer="1337x"
		)
		legit_release = TorrentResult(
			title="Dune.Part.Two.2024.720p.WEBRip.x264-GalaxyRG",
			size=1 * 1024 * 1024 * 1024,
			download_url="magnet:?xt=urn:btih:6666",
			seeders=20,
			leechers=5,
			indexer="1337x"
		)

		self.assertTrue(cam_release.is_cam)
		self.assertFalse(legit_release.is_cam)
		# Even with 2500 seeders, CAM penalty puts score far below legit 720p
		self.assertLess(cam_release.relevancy_score, 0.0)
		self.assertGreater(legit_release.relevancy_score, cam_release.relevancy_score)

	def test_file_size_penalty(self):
		# Remux 70 GB should have higher penalty than 15 GB encode
		remux = TorrentResult(
			title="Interstellar.2014.2160p.UHD.BluRay.REMUX.HEVC",
			size=70 * 1024 * 1024 * 1024,
			download_url="magnet:?xt=urn:btih:7777",
			seeders=50,
			leechers=5,
			indexer="1337x"
		)
		encode = TorrentResult(
			title="Interstellar.2014.2160p.UHD.BluRay.HEVC",
			size=15 * 1024 * 1024 * 1024,
			download_url="magnet:?xt=urn:btih:8888",
			seeders=50,
			leechers=5,
			indexer="1337x"
		)

		self.assertGreater(encode.relevancy_score, remux.relevancy_score)

	def test_sample_searches_fixtures(self):
		fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_searches.json")
		if not os.path.exists(fixture_path):
			self.skipTest("Fixture file not present")

		with open(fixture_path, "r", encoding="utf-8") as f:
			data = json.load(f)

		for key in ["Dune Part Two", "Interstellar"]:
			cards = data.get(key, [])
			if not cards:
				continue
			raw_dls = cards[0].get("downloads", [])
			results = [
				TorrentResult(
					title=d["title"],
					size=d["size"],
					download_url=d["download_url"],
					seeders=d["seeders"],
					leechers=d["leechers"],
					indexer=d["indexer"]
				)
				for d in raw_dls
			]
			agg = AggregatedResult.aggregate(results)
			self.assertTrue(len(agg) > 0)
			top_dl = agg[0].downloads[0]
			# Top download should be 2160p with positive score
			self.assertEqual(top_dl.resolution, "2160p")
			self.assertGreater(top_dl.relevancy_score, 180.0)
			# Bottom downloads should include any CAM/TS
			bottom_dls = agg[0].downloads[-5:]
			if any(d.is_cam for d in results):
				self.assertTrue(any(d.is_cam for d in bottom_dls))


if __name__ == "__main__":
	unittest.main()
