import subprocess
import json
import time
import concurrent.futures
from threading import Lock
import os
import re
import unicodedata

def sanitize_filename(filename):
    """
    Sanitize filename by removing/replacing non-UTF8 characters and reserved characters
    for cross-platform file system compatibility.
    """
    if not filename:
        return filename
    
    # Normalize unicode characters (NFD = decomposed form)
    filename = unicodedata.normalize('NFD', filename)
    
    # Remove non-ASCII characters that can't be encoded properly
    try:
        filename = filename.encode('utf-8', errors='ignore').decode('utf-8')
    except UnicodeError:
        # Fallback: replace problematic characters with spaces
        filename = ''.join(char if ord(char) < 128 else ' ' for char in filename)
    
    # Windows/filesystem reserved characters - replace with spaces
    reserved_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    
    # Replace reserved characters with spaces
    for reserved in reserved_chars:
        filename = filename.replace(reserved, ' ')
    
    # Remove control characters (0-31, 127)
    filename = ''.join(char for char in filename if ord(char) > 31 and ord(char) != 127)
    
    # Clean up multiple consecutive spaces and normalize whitespace
    filename = re.sub(r'\s+', ' ', filename)
    
    # Remove leading/trailing dots and spaces (problematic on Windows)
    filename = filename.strip('. ')
    
    # Ensure filename isn't empty after sanitization
    if not filename:
        filename = "sanitized_movie"
    
    # Truncate if too long (Windows has 260 char path limit, be conservative)
    if len(filename) > 200:
        filename = filename[:200].rstrip('. ')
    
    return filename

# Expanded list of movie names to process - SUPER SPEED TEST! 🚀
movie_names = [
    "the dark knight 2008",
    "spiderman into spiderverse", 
    "blade runner director's cut",
    "avengers endgame",
    "inception 2010",
    "pulp fiction",
    "the matrix 1999",
    "star wars episode iv",
    "the godfather",
    "interstellar 2014",
    "fight club 1999",
    "forrest gump 1994",
    "the shawshank redemption",
    "goodfellas 1990",
    "the lord of the rings fellowship",
    "jurassic park 1993",
    "terminator 2",
    "alien 1979",
    "back to the future",
    "raiders of the lost ark",
    "casino royale 2006",
    "iron man 2008",
    "deadpool 2016",
    "the departed 2006",
    "mad max fury road",
    "john wick 2014",
    "dune 2021",
    "joker 2019",
    "parasite 2019",
    "once upon a time in hollywood",
    # Adding MANY more movies for scaling test! 🎬
    "avatar 2009",
    "titanic 1997",
    "top gun maverick",
    "black panther 2018",
    "wonder woman 2017",
    "John.Wick.3.2019.1080p.Bluray.X264-EVO"
]

# Thread-safe results storage
corrected_movies = []
results_lock = Lock()

# The base FileBot command - OPTIMIZED FOR SPEED! ⚡
command_template = [
    "filebot",
    "-list",
    "--db", "TheMovieDB",
    "--format", "{json}",
    "-non-strict"
]

def process_movie_batch(movie_batch):
    """Process a batch of movies in a single FileBot call for MAXIMUM SPEED! 🔥"""
    if not movie_batch:
        return []
    
    batch_results = []
    
    try:
        # Create command with multiple queries for batch processing
        command = command_template[:]
        for movie in movie_batch:
            command.extend(["--q", movie])
        
        # Run the FileBot command for the entire batch
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse all JSON objects from the output
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines):
                if line.strip():
                    try:
                        movie_data = json.loads(line.strip())
                        movie_name = movie_data.get('name')
                        movie_year = movie_data.get('year')
                        tmdb_id = movie_data.get('id')
                        
                        if movie_name and movie_year and tmdb_id:
                            output_string = f"{movie_name} ({movie_year}) {{tmdb-{tmdb_id}}}"
                            # Sanitize the output string for filesystem compatibility
                            sanitized_output = sanitize_filename(output_string)
                            batch_results.append({
                                'query': movie_batch[i] if i < len(movie_batch) else f"batch_item_{i}",
                                'result': sanitized_output,
                                'success': True
                            })
                        
                    except (json.JSONDecodeError, IndexError):
                        continue
        
    except subprocess.CalledProcessError:
        # If batch fails, fall back to individual processing
        for movie in movie_batch:
            individual_result = process_single_movie(movie)
            if individual_result:
                batch_results.append(individual_result)
    
    return batch_results

def process_single_movie(name):
    """Process a single movie - fallback for failed batches"""
    try:
        command = command_template + ["--q", name]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        
        if result.stdout.strip():
            movie_data = json.loads(result.stdout.splitlines()[0])
            movie_name = movie_data.get('name')
            movie_year = movie_data.get('year')
            tmdb_id = movie_data.get('id')
            
            if movie_name and movie_year and tmdb_id:
                output_string = f"{movie_name} ({movie_year}) {{tmdb-{tmdb_id}}}"
                # Sanitize the output string for filesystem compatibility
                sanitized_output = sanitize_filename(output_string)
                return {
                    'query': name,
                    'result': sanitized_output,
                    'success': True
                }
        
        return {
            'query': name,
            'result': None,
            'success': False,
            'error': 'No match found'
        }
        
    except Exception as e:
        return {
            'query': name,
            'result': None,
            'success': False,
            'error': str(e)
        }

# SPEED SETTINGS - CPU CORE SCALED FOR OPTIMAL PERFORMANCE! 🚀
# Scale workers based on CPU cores
CPU_CORES = os.cpu_count()
MAX_WORKERS = min(CPU_CORES * 4, 32)  # 4x cores but cap at 32 for I/O bound tasks
BATCH_SIZE = max(4, CPU_CORES // 2)   # Scale batch size with cores

print("🚀 SUPER SPEED FileBot Test - CPU CORE SCALED BATCH TESTING! 🚀")
print(f"�️  Detected {CPU_CORES} CPU cores")
print(f"⚡ Using {MAX_WORKERS} workers (scaled from {CPU_CORES} cores)")
print(f"📦 Batch size: {BATCH_SIZE} (scaled from cores)")
print(f"📊 Processing {len(movie_names)} movies with CPU-optimized settings")
print(f"🔥 Total subprocess calls: {len(movie_names) // BATCH_SIZE + (1 if len(movie_names) % BATCH_SIZE else 0)} (vs {len(movie_names)} individual)")
print(f"📈 Expected performance gain: {len(movie_names) / (len(movie_names) // BATCH_SIZE + (1 if len(movie_names) % BATCH_SIZE else 0)):.1f}x fewer calls!")
print("=" * 80)

# Start the speed timer! ⏱️
start_time = time.time()

# Create batches for parallel processing
movie_batches = [movie_names[i:i + BATCH_SIZE] for i in range(0, len(movie_names), BATCH_SIZE)]

print(f"🔥 Created {len(movie_batches)} batches for parallel processing!")
print("🏃‍♂️ Starting parallel execution...\n")

# Process batches in parallel for MAXIMUM SPEED!
with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    # Submit all batches for parallel processing
    future_to_batch = {executor.submit(process_movie_batch, batch): batch for batch in movie_batches}
    
    batch_count = 0
    for future in concurrent.futures.as_completed(future_to_batch):
        batch_count += 1
        batch = future_to_batch[future]
        
        try:
            batch_results = future.result()
            
            # Thread-safe result collection
            with results_lock:
                for result in batch_results:
                    if result['success']:
                        corrected_movies.append(result['result'])
                        print(f"✅ Found: {result['query']} -> {result['result']}")
                    else:
                        print(f"❌ Error processing '{result['query']}': {result.get('error', 'Unknown error')}")
            
            print(f"📦 Batch {batch_count}/{len(movie_batches)} completed ({len(batch)} movies)")
            
        except Exception as exc:
            print(f"❌ Batch generated an exception: {exc}")
            # Fallback to individual processing for failed batch
            for movie in batch:
                result = process_single_movie(movie)
                if result and result['success']:
                    with results_lock:
                        corrected_movies.append(result['result'])
                    print(f"✅ Found (fallback): {result['query']} -> {result['result']}")

# Calculate speed metrics! 📈
end_time = time.time()
total_time = end_time - start_time
movies_per_second = len(movie_names) / total_time if total_time > 0 else 0

print("\n" + "=" * 80)
print("🏁 CPU-SCALED BATCH PERFORMANCE RESULTS 🏁")
print(f"🖥️  CPU cores detected: {CPU_CORES}")
print(f"⚡ Workers used: {MAX_WORKERS} ({MAX_WORKERS/CPU_CORES:.1f}x cores)")
print(f"📦 Batch size used: {BATCH_SIZE}")
print(f"⏱️  Total time: {total_time:.2f} seconds")
print(f"🎬 Movies processed: {len(movie_names)}")
print(f"✅ Successful matches: {len(corrected_movies)}")
print(f"📊 Success rate: {len(corrected_movies)/len(movie_names)*100:.1f}%")
print(f"🚀 Processing speed: {movies_per_second:.2f} movies per second")
print(f"⚡ Average time per movie: {total_time/len(movie_names):.3f} seconds")
print(f"📦 Batches processed: {len(movie_batches)}")
print(f"🔥 Batch efficiency: {len(movie_names)/len(movie_batches):.1f} movies per batch")
print(f"💪 Performance improvement: {len(movie_batches):.0f} batches vs {len(movie_names)} individual calls!")
print("=" * 80)

print("\n🎯 Sample of corrected names (showing first 10 and last 10):")
if len(corrected_movies) <= 20:
    # If 20 or fewer results, show all
    for i, movie in enumerate(corrected_movies, 1):
        print(f"{i:3d}. {movie}")
else:
    # Show first 10
    for i in range(10):
        if i < len(corrected_movies):
            print(f"{i+1:3d}. {corrected_movies[i]}")
    
    if len(corrected_movies) > 20:
        print("    ... (middle results omitted for brevity) ...")
    
    # Show last 10
    for i in range(max(10, len(corrected_movies) - 10), len(corrected_movies)):
        print(f"{i+1:3d}. {corrected_movies[i]}")

print(f"\n📋 Complete results: {len(corrected_movies)} successful movie matches found!")