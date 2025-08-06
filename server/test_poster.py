import subprocess
import re
import time
import json

def generate_clean_query(filename):
    """Cleans a messy filename into a simple search query."""
    # Replace periods, underscores, and dashes with spaces
    query = re.sub(r'[._-]', ' ', filename)

    # Find the year (e.g., 19xx or 20xx)
    year_match = re.search(r'\b(19|20)\d{2}\b', query)

    if year_match:
        # If a year is found, cut the string off right after it
        query = query[:year_match.end()]

    # Return the cleaned, trimmed query
    return query.strip()

def get_quality_tag(filename):
    """Extracts a quality tag based on a prioritized list of keywords."""
    # Convert filename to lowercase for case-insensitive matching
    title_lower = filename.lower()

    # Check for CAM tags first due to their low quality
    if any(tag in title_lower for tag in ["hdcam", "camrip", "hd-ts", ".ts.", "hdts", "hd cam", " ts "]):
        return "CAM"
    # Check for UHD/4K tags
    elif any(tag in title_lower for tag in ["2160p", " uhd ", ".uhd."]):
        return "UHD"
    # Check for FHD/1080p tags
    elif "1080p" in title_lower:
        return "FHD"
    # Check for generic HD tags
    elif any(tag in title_lower for tag in ["720p", "bluray", "brrip", "bdrip", "hdrip", "webrip", "web-dl"]):
        return "HD"
    # Check for SD tags
    elif any(tag in title_lower for tag in ["480p", "360p", "dvd"]):
        return "SD"
    # If no match is found, return an empty string
    else:
        return ""

# List of inputs to test
test_inputs = [
    'Dune.Part.Two.2024.JAPANESE.BDRip.x264-HOA',
    'Dune.Part.Two.2024.2160p.UHD.BluRay.H265-GAZPROM',
    'Dune.Part.Two.2024.1080p.BluRay.H264-RiSEHD',
    'Dune.Part.Two.2024.1080p.BluRay.x264-ROEN',
    'Dune.Part.Two.2024.720p.BluRay.x264-ROEN',
    'Dune.Part.Two.2024.BDRip.x264-ROEN',
    'Dune.Part.Two.2024.720p.WEB.h264-EDITH',
    'Dune.Part.Two.2024.2160p.WEB.h265-ETHEL',
    'Dune.Part.Two.2024.1080p.WEB.h264-ETHEL',
    'Dune.2021.1080p.BluRay.x264-OFT',
    'Dune.Part.One.2021.3D.1080p.BluRay.x264-PussyFoot',
    'Dune.Drifter.2020.1080p.BluRay.x264-FREEMAN',
    'Dune.Part.One.2021.BDRip.x264-CEBRAY',
    'Planet.Dune.2021.1080p.BluRay.x264-FREEMAN',
    'Planet.Dune.2021.BDRiP.x264-FREEMAN',
    'Dune.2021.1080p.WEB.H264-NAISU',
    'Dune.2021.720p.WEB.H264-NAISU',
    'Dune.1984.REMASTERED.720p.BluRay.x264-NUDE'
]

# Loop through each input string and process it
for input_string in test_inputs:
    print(f"🎬 Processing: {input_string}")

    # 1. Clean the input string to create a simple query
    search_query = generate_clean_query(input_string)
    print(f"    Cleaned Query: '{search_query}'")

    # 2. Use the clean query in the FileBot command with JSON output format
    command = [
        "filebot",
        "-list",
        "--q", search_query,
        "--db", "TheMovieDB",
        "--format", "{json}", # Request JSON output
        "--log", "off"        # Suppress extra logging for clean JSON
    ]

    try:
        # Start timer
        start_time = time.monotonic()
        
        # Run the command
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        # Stop timer
        end_time = time.monotonic()
        duration = end_time - start_time
        
        # FileBot returns a JSON object for each match on a new line.
        # We'll parse the first line for the top match.
        first_match_json = result.stdout.strip().split('\n')[0]
        data = json.loads(first_match_json)
        
        # Extract information from the parsed JSON data
        name = data.get('name', 'Unknown Title')
        year = data.get('year', 'N/A')
        tmdb_id = data.get('tmdbId', 0)
        
        # Get the quality tag from the original filename
        quality_tag = get_quality_tag(input_string)

        # Print the final formatted result
        print(f"    ✅ Result ({duration:.2f}s):")
        print(f"       {name} ({year}) {{tmdb-{tmdb_id}}}")
        print(f"       Quality Tag: {quality_tag}")

    except FileNotFoundError:
        print("    Error: 'filebot' command not found. 🤷‍♂️")
        break # Stop the loop if filebot isn't found
    except (subprocess.CalledProcessError, json.JSONDecodeError, IndexError):
        # This catches errors from FileBot, bad JSON, or no results
        print("    ❌ An error occurred or FileBot could not find a match.")
        
    # Print a separator for the next item
    print("-" * 50)