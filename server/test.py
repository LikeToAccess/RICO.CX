import subprocess
import json
import time
import concurrent.futures
from threading import Lock
#import os

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
    "aquaman 2018",
    "batman begins 2005",
    "superman 1978",
    "spiderman 2002",
    "x-men 2000",
    "fantastic four 2005",
    "thor 2011",
    "captain america first avenger",
    "guardians of the galaxy",
    "ant-man 2015",
    "doctor strange 2016",
    "black widow 2021",
    "eternals 2021",
    "shang-chi 2021",
    "fast and furious 2001",
    "mission impossible 1996",
    "transformers 2007",
    "pacific rim 2013",
    "godzilla 2014",
    "king kong 2005",
    "star trek 2009",
    "independence day 1996",
    "die hard 1988",
    "lethal weapon 1987",
    "predator 1987",
    "robocop 1987",
    "total recall 1990",
    "basic instinct 1992",
    "heat 1995",
    "the rock 1996",
    "con air 1997",
    "face off 1997",
    "armageddon 1998",
    "deep impact 1998",
    "saving private ryan 1998",
    "the mummy 1999",
    "gladiator 2000",
    "cast away 2000",
    "minority report 2002",
    "signs 2002",
    "the bourne identity 2002",
    "kill bill volume 1",
    "kill bill volume 2",
    "collateral 2004",
    "crash 2004",
    "million dollar baby 2004",
    "batman begins 2005",
    "war of the worlds 2005",
    "crash 2005",
    "the prestige 2006",
    "300 2007",
    "no country for old men 2007",
    "there will be blood 2007",
    "the bourne ultimatum 2007",
    "wall-e 2008",
    "slumdog millionaire 2008",
    "the curious case of benjamin button 2008",
    "district 9 2009",
    "up 2009",
    "inglourious basterds 2009",
    "zombieland 2009",
    "shutter island 2010",
    "toy story 3 2010",
    "social network 2010",
    "true grit 2010",
    "black swan 2010",
    "source code 2011",
    "super 8 2011",
    "drive 2011",
    "moneyball 2011",
    "the artist 2011",
    "the avengers 2012",
    "skyfall 2012",
    "django unchained 2012",
    "life of pi 2012",
    "argo 2012",
    "zero dark thirty 2012",
    "gravity 2013",
    "12 years a slave 2013",
    "her 2013",
    "wolf of wall street 2013",
    "captain america winter soldier",
    "guardians of the galaxy 2014",
    "birdman 2014",
    "whiplash 2014",
    "gone girl 2014",
    "the grand budapest hotel 2014",
    "ex machina 2015",
    "the revenant 2015",
    "spotlight 2015",
    "the big short 2015",
    "bridge of spies 2015",
    "la la land 2016",
    "moonlight 2016",
    "manchester by the sea 2016",
    "arrival 2016",
    "hacksaw ridge 2016",
    "hell or high water 2016",
    "get out 2017",
    "the shape of water 2017",
    "three billboards outside ebbing missouri",
    "lady bird 2017",
    "phantom thread 2017",
    "call me by your name 2017",
    "green book 2018",
    "bohemian rhapsody 2018",
    "a star is born 2018",
    "vice 2018",
    "roma 2018",
    "the favourite 2018",
    "1917 2019",
    "jojo rabbit 2019",
    "little women 2019",
    "marriage story 2019",
    "the irishman 2019",
    "ford v ferrari 2019",
    "nomadland 2020",
    "minari 2020",
    "promising young woman 2020",
    "sound of metal 2020",
    "the trial of the chicago 7 2020",
    "mank 2020",
    "coda 2021",
    "the power of the dog 2021",
    "west side story 2021",
    "king richard 2021",
    "dont look up 2021",
    "licorice pizza 2021",
    "everything everywhere all at once 2022",
    "top gun maverick 2022",
    "tar 2022",
    "the banshees of inisherin 2022",
    "elvis 2022",
    "avatar the way of water 2022",
    "this is a fake movie 12345", # Example of a movie that won't be found
    "another fake movie 98765",
    "nonexistent film 2023"
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
                            batch_results.append({
                                'query': movie_batch[i] if i < len(movie_batch) else f"batch_item_{i}",
                                'result': output_string,
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
                return {
                    'query': name,
                    'result': output_string,
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

# SPEED SETTINGS - OPTIMIZED FOR LARGE SCALE TESTING! 🚀
BATCH_SIZE = 8  # Optimal batch size for reliability and speed
MAX_WORKERS = 20  # Parallel workers for large dataset processing

print("🚀 SUPER SPEED FileBot Test - LARGE SCALE BATCH TESTING! 🚀")
print(f"📊 Processing {len(movie_names)} movies with {MAX_WORKERS} parallel workers")
print(f"⚡ Batch size: {BATCH_SIZE} movies per batch")
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
print("🏁 LARGE SCALE BATCH PERFORMANCE RESULTS 🏁")
print(f"⏱️  Total time: {total_time:.2f} seconds")
print(f"🎬 Movies processed: {len(movie_names)}")
print(f"✅ Successful matches: {len(corrected_movies)}")
print(f"📊 Success rate: {len(corrected_movies)/len(movie_names)*100:.1f}%")
print(f"🚀 Processing speed: {movies_per_second:.2f} movies per second")
print(f"⚡ Average time per movie: {total_time/len(movie_names):.3f} seconds")
print(f"📦 Batches processed: {len(movie_batches)}")
print(f"🔥 Batch efficiency: {len(movie_names)/len(movie_batches):.1f} movies per batch")
print(f"💪 Performance improvement: {len(movie_names)/len(movie_batches):.1f}x fewer subprocess calls!")
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