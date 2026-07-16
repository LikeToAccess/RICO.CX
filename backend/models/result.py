import re
from typing import List, Dict, Any

class TorrentResult:
    def __init__(self, title: str, size: int, download_url: str, seeders: int, leechers: int, indexer: str, guid: str = None, info_hash: str = None):
        self.title = title
        self.size = size
        self.download_url = download_url
        self.seeders = seeders
        self.leechers = leechers
        self.indexer = indexer
        self.guid = guid
        self.info_hash = info_hash
        
        # Parsed attributes
        self.clean_title = ""
        self.year = None
        self.resolution = "Unknown"
        self.codec = "Unknown"
        self.source = "Unknown"
        self.features = []
        self.audio = []
        self.season = None
        self.episode = None
        self.is_tv = False
        
        self._parse_metadata()

    def _parse_metadata(self):
        title_lower = self.title.lower()
        
        # 1. Detect TV show season/episode patterns
        # S01E02, S1E2, Season 1 Episode 2, E01, Ep.01, S01, etc.
        tv_match = re.search(r'\b[sS](\d{1,2})[eE](\d{1,2})\b', self.title)
        if tv_match:
            self.is_tv = True
            self.season = int(tv_match.group(1))
            self.episode = int(tv_match.group(2))
        else:
            season_match = re.search(r'\b[sS]eason\s*(\d{1,2})\b', self.title, re.IGNORECASE)
            if season_match:
                self.is_tv = True
                self.season = int(season_match.group(1))
                
            episode_match = re.search(r'\b(?:[eE]pisode|[eE]p|[eE])\s*(\d{1,2})\b', self.title, re.IGNORECASE)
            if episode_match:
                self.is_tv = True
                self.episode = int(episode_match.group(1))

        # 2. Detect Year
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', self.title)
        if year_match:
            self.year = int(year_match.group(1))

        # 3. Determine clean title boundary
        split_indices = []
        if year_match:
            split_indices.append(year_match.start())
        if tv_match:
            split_indices.append(tv_match.start())
        
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

        # Codec detection
        codec_match = re.search(r'\b(x264|x265|hevc|h264|h265|av1|divx|xvid)\b', title_lower)
        if codec_match:
            self.codec = codec_match.group(1).upper()

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

    @classmethod
    def from_prowlarr(cls, data: dict):
        title = data.get("title", "Unknown Release")
        size = data.get("size", 0)
        # Prowlarr returns downloadUrl or magnetUrl
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

    def to_dict(self) -> dict:
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
            "is_tv": self.is_tv
        }


class AggregatedResult:
    def __init__(self, clean_title: str, year: int, is_tv: bool):
        self.clean_title = clean_title
        self.year = year
        self.is_tv = is_tv
        self.downloads: List[TorrentResult] = []
        self.poster_url = None

    def add_result(self, result: TorrentResult):
        self.downloads.append(result)

    @property
    def resolutions(self) -> List[str]:
        res = set(d.resolution for d in self.downloads if d.resolution != "Unknown")
        return sorted(list(res))

    @property
    def features(self) -> List[str]:
        feats = set()
        for d in self.downloads:
            feats.update(d.features)
        return sorted(list(feats))

    @property
    def audio(self) -> List[str]:
        auds = set()
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
        
        def format_size(size_bytes):
            if size_bytes == 0:
                return "0 B"
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024
            return f"{size_bytes:.1f} PB"

        if min_size == max_size:
            return format_size(min_size)
        return f"{format_size(min_size)} - {format_size(max_size)}"

    @classmethod
    def aggregate(cls, results: List[TorrentResult]) -> List['AggregatedResult']:
        groups: Dict[tuple, 'AggregatedResult'] = {}
        for r in results:
            key = (r.clean_title.lower(), r.year, r.is_tv)
            if key not in groups:
                groups[key] = cls(r.clean_title, r.year, r.is_tv)
            groups[key].add_result(r)
        
        # Sort downloads inside each aggregated card by seeders descending
        for agg in groups.values():
            agg.downloads.sort(key=lambda x: x.seeders, reverse=True)
            
        # Sort cards by sum of seeders descending
        aggregated_list = list(groups.values())
        aggregated_list.sort(key=lambda x: sum(d.seeders for d in x.downloads), reverse=True)
        return aggregated_list

    def to_dict(self) -> dict:
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