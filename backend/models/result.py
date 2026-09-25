import math
import re
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

T = TypeVar("T", bound="TorrentResult")
A = TypeVar("A", bound="AggregatedResult")


class TorrentResult:
	"""
	Represents an individual torrent result returned by a tracker or indexer.
	"""
	def __init__(
		self,
		title: str,
		size: int,
		download_url: str,
		seeders: int,
		leechers: int,
		indexer: str,
		guid: Optional[str] = None,
		info_hash: Optional[str] = None
	) -> None:
		self.title = title
		self.size = size
		self.download_url = download_url
		self.seeders = seeders
		self.leechers = leechers
		self.indexer = indexer
		self.guid = guid
		self.info_hash = info_hash

		# Parsed attributes
		self.clean_title: str = ""
		self.year: Optional[int] = None
		self.resolution: str = "Unknown"
		self.codec: str = "Unknown"
		self.source: str = "Unknown"
		self.features: List[str] = []
		self.audio: List[str] = []
		self.season: Optional[int] = None
		self.episode: Optional[int] = None
		self.is_tv: bool = False
		self.is_ai: bool = False
		self.is_cam: bool = False
		self.relevancy_score: float = 0.0

		self._parse_metadata()

	def _parse_metadata(self) -> None:
		title_lower = self.title.lower()
		tv_match_pos: Optional[int] = None

		# 1. Detect S01E02, S1E2, S01E01-E04, S01E01-04
		s_e_match = re.search(r'\b[sS](\d{1,2})[eE](\d{1,2})\b', self.title)
		if s_e_match:
			self.is_tv = True
			self.season = int(s_e_match.group(1))
			self.episode = int(s_e_match.group(2))
			tv_match_pos = s_e_match.start()

		# 2. Detect 1x02, 01x02
		if not self.is_tv:
			x_match = re.search(r'\b(\d{1,2})x(\d{1,2})\b', self.title)
			if x_match:
				self.is_tv = True
				self.season = int(x_match.group(1))
				self.episode = int(x_match.group(2))
				tv_match_pos = x_match.start()

		# 3. Explicit Season: Season 1, Seasons 1-3, Season.01, Season_1
		if self.season is None:
			season_match = re.search(r'\b[sS]eason[s]?[\s._-]*(\d{1,2})\b', self.title, re.IGNORECASE)
			if season_match:
				self.is_tv = True
				self.season = int(season_match.group(1))
				if tv_match_pos is None or season_match.start() < tv_match_pos:
					tv_match_pos = season_match.start()

		# 4. Standalone Season token: S01, S1, S01-S03, S01-03
		if self.season is None:
			s_match = re.search(r'\b[sS](\d{1,2})\b', self.title)
			if s_match:
				self.is_tv = True
				self.season = int(s_match.group(1))
				if tv_match_pos is None or s_match.start() < tv_match_pos:
					tv_match_pos = s_match.start()

		# 5. Explicit Episode word: Episode 1, Ep 1, Ep.01, Ep_01
		if self.episode is None:
			ep_match = re.search(r'\b(?:[eE]pisode|[eE]p)[\s._-]*(\d{1,2})\b', self.title, re.IGNORECASE)
			if ep_match:
				self.is_tv = True
				self.episode = int(ep_match.group(1))
				if tv_match_pos is None or ep_match.start() < tv_match_pos:
					tv_match_pos = ep_match.start()

		# 6. Standalone Episode token: E01, E1
		if self.episode is None:
			e_match = re.search(r'\b[eE](\d{1,2})\b', self.title)
			if e_match:
				self.is_tv = True
				self.episode = int(e_match.group(1))
				if tv_match_pos is None or e_match.start() < tv_match_pos:
					tv_match_pos = e_match.start()

		# 7. Complete Series / Complete Season / Season Pack / Series Pack keywords
		if not self.is_tv:
			series_kw = re.search(r'\b(?:complete[\s._-]+(?:series|season)|season[\s._-]+pack|series[\s._-]+pack)\b', title_lower)
			if series_kw:
				self.is_tv = True
				if tv_match_pos is None or series_kw.start() < tv_match_pos:
					tv_match_pos = series_kw.start()

		# Detect Year
		year_match = re.search(r'\b(19\d{2}|20\d{2})\b', self.title)
		if year_match:
			self.year = int(year_match.group(1))

		# Determine clean title boundary
		split_indices: List[int] = []
		if year_match:
			split_indices.append(year_match.start())
		if tv_match_pos is not None:
			split_indices.append(tv_match_pos)

		# Resolution detection
		res_match = re.search(r'\b(2160p|1080p|720p|480p|360p|4k|8k)\b', title_lower)
		if res_match:
			split_indices.append(res_match.start())
			val = res_match.group(1)
			if val in ['4k', '8k']:
				self.resolution = '2160p' if val == '4k' else '4320p'
			else:
				self.resolution = val
		elif '2160' in title_lower or 'uhd' in title_lower:
			self.resolution = '2160p'
		elif '1080' in title_lower:
			self.resolution = '1080p'
		elif '720' in title_lower:
			self.resolution = '720p'

		# Extract title before the split point
		if split_indices:
			first_split = min(split_indices)
			raw_clean = self.title[:first_split]
		else:
			raw_clean = self.title

		# Clean punctuation and extra spaces
		raw_clean = re.sub(r'[\.\-\_\+\[\]\(\)\:\,]', ' ', raw_clean)
		self.clean_title = ' '.join(raw_clean.split()).strip()

		# Check for season subtitle following season/episode notation
		sub_match = re.search(r'\b[sS]\d{1,2}[\s._-]*[:\-][\s._-]*([A-Za-z0-9\s._-]+?)(?=[\s._-]*(?:\d{3,4}p|4k|8k|web|bluray|hdtv|nf|\(|\[|$))', self.title)
		if sub_match:
			sub_text = re.sub(r'[\.\-\_\+\[\]\(\)\:\,]', ' ', sub_match.group(1))
			sub_clean = ' '.join(sub_text.split()).strip()
			if sub_clean and sub_clean.lower() not in ['complete', 'season', 'pack', 'series']:
				self.clean_title = f"{self.clean_title} {sub_clean}".strip()

		# Codec detection
		codec_match = re.search(r'\b(x264|x265|hevc|h264|h\.264|h265|h\.265|av1|divx|xvid)\b', title_lower)
		if codec_match:
			self.codec = codec_match.group(1).replace('.', '').upper()

		# Source detection
		source_match = re.search(r'\b(bluray|blu-ray|web-dl|webdl|webrip|web|brrip|bdrip|dvdrip|hdtv)\b', title_lower)
		if source_match:
			self.source = source_match.group(1).replace('-', '').upper()

		# Features detection
		features_list = {
			'hdr10+': 'HDR10+',
			'hdr10': 'HDR10',
			'hdr': 'HDR',
			'dv': 'DV',
			'dolby vision': 'DV',
			'10bit': '10bit',
			'10-bit': '10bit'
		}
		for pattern, label in features_list.items():
			if re.search(r'\b' + re.escape(pattern) + r'\b', title_lower):
				if label not in self.features:
					self.features.append(label)

		# Audio detection
		audio_list = {
			'atmos': 'Atmos',
			'dts-hd': 'DTS-HD',
			'dts': 'DTS',
			'truehd': 'TrueHD',
			'dd5.1': 'DD5.1',
			'ac3': 'AC3',
			'dd+7.1': 'DD+7.1',
			'aac': 'AAC',
			'5.1': '5.1',
			'7.1': '7.1'
		}
		for pattern, label in audio_list.items():
			if re.search(r'\b' + re.escape(pattern) + r'\b', title_lower):
				if label not in self.audio:
					self.audio.append(label)

		# AI upscale detection
		ai_match = re.search(
			r'\b(?:ai[\s._-]*(?:upscale[d]?|enhance[d]?|remaster[a-z]*|uhd|4k|2160p)|upscale[d]?|topaz|esrgan|rife|waifu2x)\b',
			title_lower
		)
		if ai_match:
			self.is_ai = True

		# CAM / Telesync / Telecine detection
		cam_match = re.search(
			r'\b(?:cam|camrip|hdcam|hd[\s._-]?ts|telesync|pdvd|telecine|hd[\s._-]?tc|ts|tc)\b',
			title_lower
		)
		if cam_match:
			self.is_cam = True

		self.relevancy_score = self._calculate_relevancy_score()

	def _calculate_relevancy_score(self) -> float:
		"""
		Calculates a relevancy score based on quality preferences:
		Resolution > Codec > Atmos > Dolby Vision > HDR > File Size (penalty) > Seeders > AI (penalty) > CAM (disqualification).
		"""
		score = 0.0

		# 1. Resolution
		res_weights = {
			"2160p": 100.0,
			"4320p": 100.0,
			"1080p": 60.0,
			"720p": 25.0,
			"480p": 10.0,
			"Unknown": 5.0
		}
		score += res_weights.get(self.resolution, 5.0)

		# 2. Codec
		codec_weights = {
			"AV1": 45.0,
			"HEVC": 40.0,
			"X265": 40.0,
			"H265": 40.0,
			"H264": 20.0,
			"X264": 20.0,
			"AVC": 20.0,
			"XVID": -20.0,
			"DIVX": -20.0
		}
		score += codec_weights.get(self.codec, 0.0)

		# 3. Audio (Dolby Atmos)
		title_lower = self.title.lower()
		has_atmos = "Atmos" in self.audio or bool(re.search(r'\batmos\b', title_lower))
		if has_atmos:
			score += 30.0

		# 4. Dolby Vision
		has_dv = "DV" in self.features or bool(re.search(r'\b(?:dv|dolby[\s._-]?vision)\b', title_lower))
		if has_dv:
			score += 25.0

		# 5. HDR (HDR, HDR10, HDR10+)
		has_hdr = any(x in self.features for x in ["HDR", "HDR10", "HDR10+"]) or bool(re.search(r'\bhdr(?:10(?:\+)?)?\b', title_lower))
		if has_hdr:
			score += 20.0

		# 6. File Size Penalty (-0.7 pt per GB / -1 pt per ~1.4 GB, max -48 pts)
		gb = self.size / (1024 ** 3)
		score -= min(48.0, gb * 0.7)

		# 7. Seeders (Diminishing logarithmic scale)
		if self.seeders > 0:
			score += min(50.0, 15.0 * math.log10(self.seeders + 1))
		else:
			score -= 50.0

		# 8. AI Penalty (Guarantees dropping below 720p releases)
		if self.is_ai:
			score -= 200.0

		# 9. CAM / Telesync Penalty (Quarantines theatrical recordings at the bottom)
		if self.is_cam:
			score -= 300.0

		return round(score, 1)

	@classmethod
	def from_prowlarr(cls: Type[T], data: Dict[str, Any]) -> T:
		title = data.get("title", "Unknown Release")
		size = data.get("size", 0)
		download_url = data.get("downloadUrl") or data.get("magnetUrl") or ""
		seeders = data.get("seeders", 0)
		leechers = data.get("leechers", 0)
		indexer = data.get("indexer", "Unknown Indexer")
		guid = data.get("guid", "")
		info_hash = data.get("infoHash", "")

		return cls(
			title=title,
			size=size,
			download_url=download_url,
			seeders=seeders,
			leechers=leechers,
			indexer=indexer,
			guid=guid,
			info_hash=info_hash
		)

	def to_dict(self) -> Dict[str, Any]:
		return {
			"title": self.title,
			"size": self.size,
			"download_url": self.download_url,
			"seeders": self.seeders,
			"leechers": self.leechers,
			"indexer": self.indexer,
			"guid": self.guid,
			"info_hash": self.info_hash,
			"clean_title": self.clean_title,
			"year": self.year,
			"resolution": self.resolution,
			"codec": self.codec,
			"source": self.source,
			"features": self.features,
			"audio": self.audio,
			"season": self.season,
			"episode": self.episode,
			"is_tv": self.is_tv,
			"is_ai": self.is_ai,
			"is_cam": self.is_cam,
			"relevancy_score": self.relevancy_score
		}


class AggregatedResult:
	"""
	Aggregates multiple TorrentResults into a unified media card.
	"""
	def __init__(self, clean_title: str, year: Optional[int], is_tv: bool) -> None:
		self.clean_title = clean_title
		self.year = year
		self.is_tv = is_tv
		self.downloads: List[TorrentResult] = []
		self.poster_url: Optional[str] = None

	def add_result(self, result: TorrentResult) -> None:
		self.downloads.append(result)

	@property
	def resolutions(self) -> List[str]:
		res = set(d.resolution for d in self.downloads if d.resolution != "Unknown")
		return sorted(list(res))

	@property
	def features(self) -> List[str]:
		feats: set[str] = set()
		for d in self.downloads:
			feats.update(d.features)
		return sorted(list(feats))

	@property
	def audio(self) -> List[str]:
		auds: set[str] = set()
		for d in self.downloads:
			auds.update(d.audio)
		return sorted(list(auds))

	@property
	def total_size_range(self) -> str:
		if not self.downloads:
			return "0 B"
		sizes = [d.size for d in self.downloads]
		min_size = min(sizes)
		max_size = max(sizes)

		def format_size(size_bytes: float) -> str:
			if size_bytes == 0:
				return "0 B"
			for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
				if size_bytes < 1024:
					return f"{size_bytes:.1f} {unit}"
				size_bytes /= 1024
			return f"{size_bytes:.1f} PB"

		if min_size == max_size:
			return format_size(float(min_size))
		return f"{format_size(float(min_size))} - {format_size(float(max_size))}"

	@classmethod
	def aggregate(cls: Type[A], results: List[TorrentResult]) -> List[A]:
		groups: Dict[Tuple[str, Optional[int], bool], A] = {}
		for r in results:
			key = (r.clean_title.lower(), r.year, r.is_tv)
			if key not in groups:
				groups[key] = cls(r.clean_title, r.year, r.is_tv)
			groups[key].add_result(r)

		for agg in groups.values():
			agg.downloads.sort(key=lambda x: (x.relevancy_score, x.seeders), reverse=True)

		aggregated_list = list(groups.values())
		aggregated_list.sort(key=lambda x: sum(d.seeders for d in x.downloads), reverse=True)
		return aggregated_list

	def to_dict(self) -> Dict[str, Any]:
		return {
			"clean_title": self.clean_title,
			"year": self.year,
			"is_tv": self.is_tv,
			"resolutions": self.resolutions,
			"features": self.features,
			"audio": self.audio,
			"size_range": self.total_size_range,
			"poster_url": self.poster_url,
			"downloads": [d.to_dict() for d in self.downloads]
		}