# Discovarr

## Creating Placeholders and Downloading Real

Since you already have the Watchlist-to-Seerr automation handling the heavy lifting of acquisition, all we need to do is build the visual facade in Plex.

Here is the exact blueprint to create the dummy file, tag it via Tautulli and Python, and badge it with Kometa.

### 1. Generating a Bulletproof Dummy File

To ensure Plex’s scanner always registers the file as valid media without choking, we use `ffmpeg` to generate a 1-second, black-screen video file with silent audio.

Run this command in your terminal to create your template file:

```bash
ffmpeg -f lavfi -i color=size=1920x1080:rate=24:color=black -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -t 1 dummy.mkv

```

### 2. The Cleanup Script

This version adds the `removeLabel()` function to strip the tag so Kometa knows to drop the badge, and uses `emptyTrash()` on just the discovery library to wipe the UI clean without relying on global Plex settings.

```python
import os
import shutil
import sys
from plexapi.server import PlexServer

# 1. Configuration
PLEX_URL = 'http://YOUR_PLEX_IP:32400'
PLEX_TOKEN = 'YOUR_PLEX_TOKEN'
DISCOVERY_LIBRARY_NAME = 'discover_shows'
LABEL_NAME = 'Placeholder'

def main():
    # Ensure Tautulli passed the show title
    if len(sys.argv) < 2:
        print("Error: No show title provided.")
        sys.exit(1)
        
    show_title = sys.argv[1]
    
    # 2. Connect to Plex
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    discovery_lib = plex.library.section(DISCOVERY_LIBRARY_NAME)
    
    try:
        # 3. Search for the exact show title in the dummy library
        print(f"Searching for '{show_title}' in {DISCOVERY_LIBRARY_NAME}...")
        results = discovery_lib.search(title=show_title, libtype='show')
        
        if not results:
            print("No matching dummy show found. No cleanup needed.")
            return
            
        dummy_show = results[0] 
        
        # 4. Remove the Tag
        dummy_show.removeLabel(LABEL_NAME)
        print(f"Success: Removed '{LABEL_NAME}' label from '{dummy_show.title}'")
        
        # 5. Get the physical folder path and delete it
        locations = dummy_show.locations
        if locations:
            folder_to_delete = locations[0]
            if os.path.exists(folder_to_delete):
                shutil.rmtree(folder_to_delete)
                print(f"Success: Deleted dummy folder at {folder_to_delete}")
            
        # 6. Update library and empty the trash surgically
        discovery_lib.update()
        discovery_lib.emptyTrash()
        print(f"Triggered scan and emptied trash for {DISCOVERY_LIBRARY_NAME}.")
            
    except Exception as e:
        print(f"Failed to clean up dummy file: {e}")

if __name__ == "__main__":
    main()

```

---

### 3. How It All Flows Together (The Complete Pipeline)

Here is your custom, end-to-end discovery engine from scratch:

**Phase 1: Creation & Tagging**

1. **Generate Placeholder:** You create a 1-second blank `.mkv` file (using `ffmpeg` or a script) and place it in your `discover_shows` physical folder (e.g., `/media/discover_shows/Paradise (2025)/Season 01/Paradise - S01E01.mkv`).
2. **Plex Scans:** Plex detects the new folder, scans the file, queries TMDB/TVDB, and downloads all the official posters, cast lists, and metadata into the `discover_shows` library.
3. **Tautulli Tags It:** Tautulli sees a "Recently Added" event in the `discover_shows` library. It instantly fires `tag_dummy.py`, which applies the `Placeholder` label to the show in Plex.
4. **Kometa Badges It:** On its next scheduled run, Kometa sees the `Placeholder` label and overlays your custom "Not on Server" badge onto the poster.

**Phase 2: Discovery & Request**
5. **The Couch Experience:** You sit on the couch, open Plex on your TV, and doomscroll through your beautifully populated `discover_shows` library.
6. **The Request:** You see *Paradise*, decide you want to watch it, and add it to your Plex Watchlist.
7. **Seerr Intercepts:** Seerr syncs with your Plex Watchlist. It sees *Paradise* was added, creates an automatic request, approves it, and passes the baton to Sonarr.

**Phase 3: Acquisition & Cleanup**
8. **Sonarr Downloads:** Sonarr searches your indexers, finds the real episodes of *Paradise*, downloads them, and moves them into your **real** media folder (e.g., `/media/Real TV/Paradise (2025)`).
9. **Plex Scans Real Media:** Sonarr tells Plex to scan the `Real TV` library. Plex imports the fully playable episodes.
10. **Tautulli Triggers Cleanup:** Tautulli sees a "Recently Added" event in your `Real TV` library. It fires `cleanup_dummy.py`, passing the title "Paradise" to the script.
11. **The Wipe:** The script searches `discover_shows` for "Paradise", removes the `Placeholder` tag, physically deletes the fake *Paradise* folder from your hard drive, triggers a library scan, and explicitly empties the trash for `discover_shows`.

**The Result:** The placeholder vanishes entirely from your discovery library, the real show exists flawlessly in your main library, and you never had to leave the Plex UI to make it happen.

Would you like to move on to creating the Radarr/Movie equivalent for this, or do you want to dig into customizing the Kometa overlay?

## Streaming Service Aggregator (ingestion to above section)

This is the ultimate hybrid setup. You get the broad, cultural zeitgeist of what's trending on the major streamers, combined with the hyper-personalized, algorithmic recommendations based specifically on your watch history.

To pull this off for free, we combine the **TMDB API** (which natively uses JustWatch's data for the streaming platform lists) with the **Trakt API** (utilizing Couchmoney for the watch-history recommendations).

Here is exactly how to build this dual-engine ingestion script.

### 1. The Prerequisites

* **TMDB API Key:** Go to TheMovieDB.org, create a free account, go to Settings > API, and request a Developer API key.
* **Streaming Provider IDs:** TMDB uses JustWatch's internal ID numbers for streaming services. Here are the heavy hitters in the US:
* Netflix = `8`
* Amazon Prime = `119`
* Disney+ = `337`
* Apple TV+ = `350`
* Hulu = `15`
* Max = `384`


* **Trakt / Couchmoney:** Ensure you have logged into Couchmoney.tv with your Trakt account to auto-generate your personalized recommendation lists.

### 2. The Dual-Engine Python Script

This script (`generate_dummies.py`) hits TMDB to find the most popular content currently streaming on your chosen platforms, then hits Trakt to grab your personalized Couchmoney recommendations, and generates the dummy files for both.

```python
import os
import shutil
import re
import requests
import time

# --- 1. CONFIGURATION ---
TMDB_API_KEY = 'YOUR_TMDB_API_KEY'
TRAKT_CLIENT_ID = 'YOUR_TRAKT_CLIENT_ID'
TRAKT_USERNAME = 'YOUR_TRAKT_USERNAME'

TEMPLATE_FILE = '/scripts/dummy_template/dummy.mkv'
DISCOVER_MOVIES_PATH = '/media/discover_movies'
DISCOVER_SHOWS_PATH = '/media/discover_shows'
REAL_MOVIES_PATH = '/media/real_movies'
REAL_SHOWS_PATH = '/media/real_shows'

# --- 2. THE DATA SOURCES ---
# TMDB: List the JustWatch provider IDs you want to scrape
STREAMING_PROVIDERS = ['8', '15', '350', '384'] # Netflix, Hulu, Apple TV+, Max
WATCH_REGION = 'US'

# Trakt: Your Couchmoney recommendation list slugs
TRAKT_LISTS = [
    'recommendations-movies', # Replace with your actual Couchmoney movie slug
    'recommendations-shows'   # Replace with your actual Couchmoney show slug
]

# --- 3. HELPER FUNCTIONS ---
def sanitize_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", str(title)).strip()

def create_dummy(title, year, media_type):
    # Skip items without a valid year
    if not year or year == 'Unknown':
        return

    folder_name = f"{sanitize_filename(title)} ({year})"
    
    if media_type in ['movie', 'movies']:
        if os.path.exists(os.path.join(REAL_MOVIES_PATH, folder_name)) or \
           os.path.exists(os.path.join(DISCOVER_MOVIES_PATH, folder_name)):
            return 
            
        target_dir = os.path.join(DISCOVER_MOVIES_PATH, folder_name)
        os.makedirs(target_dir, exist_ok=True)
        shutil.copyfile(TEMPLATE_FILE, os.path.join(target_dir, f"{folder_name}.mkv"))
        print(f"[+] Added Movie: {folder_name}")

    elif media_type in ['show', 'shows', 'tv']:
        if os.path.exists(os.path.join(REAL_SHOWS_PATH, folder_name)) or \
           os.path.exists(os.path.join(DISCOVER_SHOWS_PATH, folder_name)):
            return 
            
        target_dir = os.path.join(DISCOVER_SHOWS_PATH, folder_name, "Season 01")
        os.makedirs(target_dir, exist_ok=True)
        shutil.copyfile(TEMPLATE_FILE, os.path.join(target_dir, f"{folder_name} - S01E01.mkv"))
        print(f"[+] Added Show: {folder_name}")

# --- 4. TMDB JUSTWATCH ENGINE ---
def fetch_tmdb_streaming():
    print("\n--- Fetching Popular Streaming Content via TMDB ---")
    
    # We will join our provider IDs into a string like "8|15|350" (OR logic)
    provider_string = "|".join(STREAMING_PROVIDERS)
    
    endpoints = {
        'movie': f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&watch_region={WATCH_REGION}&with_watch_providers={provider_string}&sort_by=popularity.desc",
        'tv': f"https://api.themoviedb.org/3/discover/tv?api_key={TMDB_API_KEY}&watch_region={WATCH_REGION}&with_watch_providers={provider_string}&sort_by=popularity.desc"
    }

    for media_type, url in endpoints.items():
        try:
            response = requests.get(url)
            if response.status_code == 200:
                results = response.json().get('results', [])
                for item in results:
                    # TMDB handles TV and Movie title/year keys slightly differently
                    if media_type == 'movie':
                        title = item.get('title')
                        year = item.get('release_date', '')[:4]
                    else:
                        title = item.get('name')
                        year = item.get('first_air_date', '')[:4]
                        
                    create_dummy(title, year, media_type)
            else:
                print(f"TMDB API Error: {response.status_code}")
        except Exception as e:
            print(f"Request failed: {e}")
            
        time.sleep(1) # Be polite to the API

# --- 5. TRAKT RECOMMENDATION ENGINE ---
def fetch_trakt_recommendations():
    print("\n--- Fetching Personalized Recommendations via Trakt ---")
    headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': TRAKT_CLIENT_ID
    }
    
    for list_slug in TRAKT_LISTS:
        # Couchmoney lists are usually owned by 'couchmoney' or your own username depending on how you set it up
        url = f"https://api.trakt.tv/users/couchmoney/lists/{list_slug}/items"
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                for item in response.json():
                    m_type = item['type'] # 'movie' or 'show'
                    media_data = item[m_type]
                    year = media_data.get('year', 'Unknown')
                    title = media_data.get('title', 'Unknown Title')
                    
                    create_dummy(title, year, m_type)
            else:
                print(f"Trakt API Error for {list_slug}: {response.status_code}")
        except Exception as e:
            print(f"Request failed: {e}")
            
        time.sleep(2) # Be polite to the API

if __name__ == "__main__":
    fetch_tmdb_streaming()
    fetch_trakt_recommendations()
    print("\n[✓] Ingestion Complete!")

```

### How the TMDB Filtering Works

Look closely at the URL being built in the `endpoints` dictionary:
`...&with_watch_providers={provider_string}&sort_by=popularity.desc`

This defaults to pulling the top 20 most popular movies and shows across your selected streaming services. If you want a deeper catalog, you can loop through the API pages by appending `&page=1`, `&page=2`, etc., to the URL in your script.

You've essentially just built your own custom streaming aggregator right inside your Plex server.

Would you like me to show you how to add parameters to the TMDB API call to filter out garbage (e.g., "only show me things with an IMDB/TMDB rating of 7.0 or higher" or "exclude reality TV and documentaries")?