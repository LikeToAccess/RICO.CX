# -*- coding: utf-8 -*-
# filename          : scraper_tools.py
# description       : Helper file for scraping websites and matching filenames to TMDb.
# author            : Rico Alexander
# email             : rico@rico.cx
# date              : 08-01-2025
# version           : v3.1
# usage             : python waitress_serve.py
# notes             : This file should not be run directly.
# license           : MIT
# py version        : 3.12.5 (must run on 3.10 or higher)
#==============================================================================
import os
import subprocess
import json
import time
import concurrent.futures
import re
import unicodedata
from time import perf_counter
from collections.abc import Callable

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from tmdbv3api import TMDb, Search, Movie, TV  # type: ignore[import-untyped]

# These imports are placeholders for your actual project structure.
# You should have these defined in your project.
class FindElement:
    def __init__(self, driver): pass
class WaitUntilElement:
    def __init__(self, driver): pass
# It's better to get these from a real settings file or environment variables.
HEADLESS = True
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")


def sanitize_filename(filename):
    """
    Sanitize filename by removing/replacing non-UTF8 characters and reserved characters
    for cross-platform file system compatibility.
    """
    if not filename:
        return ""
    filename = unicodedata.normalize('NFD', filename)
    try:
        filename = filename.encode('utf-8', errors='ignore').decode('utf-8')
    except UnicodeError:
        filename = ''.join(char if ord(char) < 128 else ' ' for char in filename)

    reserved_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for reserved in reserved_chars:
        filename = filename.replace(reserved, ' ')

    filename = ''.join(char for char in filename if ord(char) > 31 and ord(char) != 127)
    filename = re.sub(r'\s+', ' ', filename).strip('. ')
    if not filename:
        return "sanitized_movie"
    return filename[:200].rstrip('. ')

def get_quality_tag(file_dict: dict) -> str:
    """Extracts quality tag from filename using the original filename data."""
    if file_dict.get("quality_tag"):
        return file_dict["quality_tag"]
    title = file_dict.get("filename_old", file_dict.get("filename", "")).lower()
    tag = ""
    if any(q in title for q in ["hdcam", "camrip", "hd-ts", ".ts.", "hdts", "hd cam", " ts "]):
        tag = "CAM"
    elif any(q in title for q in ["2160p", " uhd ", ".uhd."]):
        tag = "UHD"
    elif "1080p" in title:
        tag = "FHD"
    elif any(q in title for q in ["720p", "bluray", "brrip", "bdrip", "hdrip", "webrip", "web-dl"]):
        tag = "HD"
    elif any(q in title for q in ["480p", "360p", "dvd"]):
        tag = "SD"
    file_dict["quality_tag"] = tag
    return tag

def generate_clean_query(filename):
    """Cleans a messy filename into a simple search query."""
    query = re.sub(r'[._-]', ' ', filename)
    
    # Remove common release group patterns and quality indicators
    query = re.sub(r'\b(1080p|720p|480p|2160p|UHD|BluRay|WEB|H264|x264|HDTV|DVDRip|BDRip|WEBRip)\b', '', query, flags=re.IGNORECASE)
    query = re.sub(r'\b(CBFM|ETHEL|AccomplishedYak|DARKFLiX|CODSWALLOP|WEEB|VETO|KNiVES|D3US|EDITH|SKYFiRE|BLOOM)\b', '', query, flags=re.IGNORECASE)
    
    # Extract year and truncate after it for better matching
    year_match = re.search(r'\b(19|20)\d{2}\b', query)
    if year_match:
        query = query[:year_match.end()]
    
    # Clean up extra spaces
    query = re.sub(r'\s+', ' ', query).strip()
    
    return query


class ScraperTools(WaitUntilElement, FindElement):
    def __init__(self, init: bool = True):
        # This is a placeholder constructor. Your actual implementation may vary.
        if not init:
            return
        print("ScraperTools initialized (mock).")

class FileBot:
    def __init__(self):
        try:
            if not os.path.isdir("temp"): os.mkdir("temp")
            subprocess.run(["filebot", "-version"], check=True, capture_output=True)
            print("FileBot initialized.")
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            raise FileNotFoundError("FileBot is not installed or not in your PATH.") from e

        self.command_template = ["filebot", "-list", "--db", "TheMovieDB", "--format", "{json}", "-non-strict"]
        self.CPU_CORES = os.cpu_count() or 1
        self.MAX_WORKERS = min(self.CPU_CORES * 4, 32)
        self.BATCH_SIZE = max(4, self.CPU_CORES // 2)  # Restore original batch size

    def _process_batch(self, batch: list[dict]) -> list[dict]:
        """
        Processes a batch of file dictionaries with a single FileBot call.
        This version tries to be more resilient to partial failures.
        """
        if len(batch) == 1:
            # For single items, just use individual processing directly
            return [self.get_name(batch[0])]
            
        queries = [f'--q "{generate_clean_query(f.get("filename", ""))}"' for f in batch]
        command_str = " ".join(self.command_template + queries + ["--log", "off"])
        
        processed_batch = []
        try:
            # We remove check=True to handle cases where filebot returns a non-zero exit code
            # but still provides partial results.
            result = subprocess.run(
                command_str, capture_output=True, text=True,
                encoding='utf-8', errors='ignore', shell=True, timeout=20  # Reduced timeout
            )

            # Create a map from query to result for reliable matching
            result_map = {}
            if result.stdout and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if not line.strip():
                        continue
                    try:
                        res = json.loads(line)
                        query_key = (res.get("q", "") or "").lower().strip()
                        if query_key:
                            result_map[query_key] = res
                    except json.JSONDecodeError:
                        continue # Ignore malformed lines

            # Process the original batch, using the result map
            for file_dict in batch:
                original_filename = file_dict.get("filename", "")
                clean_query = generate_clean_query(original_filename).lower().strip()
                movie_data = result_map.get(clean_query)

                if movie_data:
                    movie_name = movie_data.get('name')
                    movie_year = movie_data.get('year')
                    tmdb_id = movie_data.get('tmdbId') or movie_data.get('id')
                    if movie_name and movie_year and tmdb_id:
                        renamed = f"{movie_name} ({movie_year}) {{tmdb-{tmdb_id}}}"
                        file_dict.update({
                            "filename": sanitize_filename(renamed),
                            "title": movie_name,
                            "release_year": str(movie_year),
                            "tmdb_id": str(tmdb_id),
                        })
                        processed_batch.append(file_dict)
                    else:
                        # Result was incomplete, fallback to individual processing
                        processed_batch.append(self.get_name(file_dict))
                else:
                    # No result for this query, fallback to individual processing
                    processed_batch.append(self.get_name(file_dict))
            
            return processed_batch

        except subprocess.TimeoutExpired:
            print(f"⚠️ Batch timed out after 20s. Falling back to individual processing.")
            return [self.get_name(file_dict) for file_dict in batch]
        except Exception as e:
            # If the whole batch process fails catastrophically, fall back for all items.
            print(f"⚠️ Batch failed unexpectedly: {e}. Falling back to individual processing.")
            return [self.get_name(file_dict) for file_dict in batch]

    def get_names_streaming(self, filenames: list[dict]):
        """
        Generator that yields results as batches complete for streaming to client.
        Yields (batch_results, progress_info) tuples.
        """
        print(f"🚀 Processing {len(filenames)} files with streaming batched workers...")
        print(f"⚡ Using up to {self.MAX_WORKERS} workers.")
        print(f"📦 Batch size per worker: {self.BATCH_SIZE}")

        start_time = time.time()
        file_batches = [filenames[i:i + self.BATCH_SIZE] for i in range(0, len(filenames), self.BATCH_SIZE)]
        print(f"🔥 Created {len(file_batches)} batches to distribute among workers.")

        completed_batches = 0
        total_results = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_batch = {executor.submit(self._process_batch, batch): batch for batch in file_batches}
            
            for future in concurrent.futures.as_completed(future_to_batch):
                try:
                    batch_results = future.result()
                    completed_batches += 1
                    total_results += len(batch_results)
                    
                    elapsed_time = time.time() - start_time
                    progress_info = {
                        "completed_batches": completed_batches,
                        "total_batches": len(file_batches),
                        "processed_files": total_results,
                        "total_files": len(filenames),
                        "elapsed_time": elapsed_time,
                        "files_per_second": total_results / elapsed_time if elapsed_time > 0 else 0
                    }
                    
                    print(f"📦 Batch {completed_batches}/{len(file_batches)} completed - streaming {len(batch_results)} results")
                    
                    # Yield the batch results and progress info
                    yield batch_results, progress_info
                    
                except Exception as exc:
                    print(f"❌ A batch generated a catastrophic exception: {exc}")
                    completed_batches += 1

        final_time = time.time() - start_time
        print(f"✅ Streaming completed in {final_time:.2f} seconds ({len(filenames) / final_time:.2f} files/s)")

    def get_names(self, filenames: list[dict]) -> list[dict]:
        """Processes a list of file dictionaries in parallel batches."""
        print(f"🚀 Processing {len(filenames)} files with batched workers...")
        print(f"⚡ Using up to {self.MAX_WORKERS} workers.")
        print(f"📦 Batch size per worker: {self.BATCH_SIZE}")

        start_time = time.time()
        file_batches = [filenames[i:i + self.BATCH_SIZE] for i in range(0, len(filenames), self.BATCH_SIZE)]
        print(f"🔥 Created {len(file_batches)} batches to distribute among workers.")

        all_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_batch = {executor.submit(self._process_batch, batch): batch for batch in file_batches}
            for i, future in enumerate(concurrent.futures.as_completed(future_to_batch), 1):
                try:
                    all_results.extend(future.result())
                    print(f"📦 Batch {i}/{len(file_batches)} completed.")
                except Exception as exc:
                    print(f"❌ A batch generated a catastrophic exception: {exc}")

        # The results are now a flat list, but potentially out of order.
        # We'll return them as is, since the calling function in scraper.py can handle it.
        # If strict ordering were needed, a map-and-reconstruct approach would be used here.
        end_time = time.time()
        total_time = end_time - start_time
        if total_time > 0:
            print(f"✅ Completed processing in {total_time:.2f} seconds ({len(filenames) / total_time:.2f} files/s)")

        return all_results

    def get_name(self, file_dict: dict) -> dict:
        """
        Processes a single file dictionary, updating it with FileBot and TMDb info.
        It preserves existing keys like 'page_url'.
        """
        filename = file_dict.get("filename", "")
        file_dict["filename_old"] = file_dict.get("filename_old", filename)
        get_quality_tag(file_dict)

        # Quick check for content that's unlikely to be in TMDb (basic documentary detection)
        documentary_keywords = ['documentary', 'behind.the.scenes', 'making.of', 'interview', 'concert', 'live.concert']
        if any(keyword in filename.lower() for keyword in documentary_keywords):
            clean_title = re.sub(r'\.(mkv|mp4|avi)$', '', filename.replace(".", " ")).strip()
            file_dict.update({
                "filename": clean_title,
                "title": clean_title,
                "release_year": "N/A",
                "tmdb_id": "",
            })
            return file_dict

        try:
            clean_query = generate_clean_query(filename)
            command = self.command_template + ["--q", clean_query, "--log", "off"]
            result = subprocess.run(
                command, capture_output=True, text=True, check=True,
                encoding='utf-8', errors='ignore', timeout=8  # Reduced timeout
            )
            # Check if stdout has content before trying to parse
            if result.stdout and result.stdout.strip():
                # FileBot may return multiple JSON objects for -non-strict queries.
                # We'll take the first one as the most likely match.
                first_line = result.stdout.strip().split('\n')[0]
                movie_data = json.loads(first_line)
                movie_name = movie_data.get('name')
                movie_year = movie_data.get('year')
                tmdb_id = movie_data.get('tmdbId') or movie_data.get('id')

                if movie_name and movie_year and tmdb_id:
                    renamed = f"{movie_name} ({movie_year}) {{tmdb-{tmdb_id}}}"
                    file_dict.update({
                        "filename": sanitize_filename(renamed),
                        "title": movie_name,
                        "release_year": str(movie_year),
                        "tmdb_id": str(tmdb_id),
                    })
                    # Successfully processed, return the updated dict
                    return file_dict
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            # Log the error for debugging but proceed to the fallback
            print(f"ℹ️  FileBot 'get_name' failed for '{filename}': {e}. Using fallback.")

        # Fallback logic: This block is now guaranteed to run if the try block fails or doesn't return.
        # This ensures 'title' is always set.
        clean_title = re.sub(r'\.(mkv|mp4|avi)$', '', filename.replace(".", " ")).strip()
        file_dict.update({
            "filename": clean_title,
            "title": clean_title,
            "release_year": "N/A",
            "tmdb_id": "",
        })
        return file_dict


class TMDbTools:
    def __init__(self):
        if not TMDB_API_KEY:
            raise ValueError("TMDb API key is missing.")
        self.tmdb = TMDb()
        self.tmdb.api_key = TMDB_API_KEY
        self.search = Search()

    def details_movie(self, movie_id: int | str) -> dict:
        return Movie().details(int(movie_id))