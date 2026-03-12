# plexflixarr

This is the definitive blueprint for your custom, zero-storage, hyper-personalized Plex discovery engine.

By building the data ingestion from scratch and utilizing Plex Smart Collections via Kometa, you avoid the nightmare of maintaining forked codebases or fighting Seerr's availability checks.

Here is the comprehensive, end-to-end implementation plan.

---

### Phase 1: Architecture and Design

Your ecosystem relies on strict **Library Isolation** to ensure your dummy files never pollute your real media database or confuse your requesting services.

**1. The Storage Layer**

* Create an empty, 1-second video file using `ffmpeg` and save it as `/scripts/dummy_template/dummy.mkv`.
* Create two new root folders on your server: `/media/discover_movies` and `/media/discover_shows`.

**2. The Plex Layer**

* Create two new Plex libraries: **Discover Movies** (pointing to `/media/discover_movies`) and **Discover Shows** (pointing to `/media/discover_shows`).
* Disable "Include in dashboard" for these libraries so dummy files don't clutter your Continue Watching or global Recently Added feeds.

**3. The Seerr Layer (The Blindfold)**

* In Seerr $\rightarrow$ Settings $\rightarrow$ Plex, **uncheck** the Discover Movies and Discover Shows libraries. This ensures Seerr remains blind to your placeholders and will accurately fulfill Watchlist requests.

---

### Phase 2: Sequence Flows

Here is how data physically moves through your automated pipeline.

#### A. The Ingestion & Tagging Flow (Nightly Cron Job)

1. **Fetch:** The custom Python script queries the TMDB API (using JustWatch provider IDs) for trending streaming media, fetching up to 100 items per provider. It then queries the Trakt API for your Couchmoney recommendation lists.
2. **Generate:** The script checks if the media exists in your *real* or *discover* folders. If not, it creates the folder structure `Show Name (Year) / Season 01` and copies the `dummy.mkv`.
3. **Scan:** The script triggers a Plex library scan on the discovery libraries and waits for it to finish downloading metadata.
4. **Tag:** The script uses `python-plexapi` to find the newly added media in Plex and applies specific metadata labels (e.g., `Discover_Netflix`, `Discover_Recs`, `Discover_SciFi`).

#### B. The Request Flow (User Driven)

1. **Browse:** You view a Kometa-generated Smart Collection in Plex (e.g., "Trending on Netflix") and click a movie with a "Request Needed" poster overlay.
2. **Request:** You click "Add to Watchlist".
3. **Fulfillment:** Seerr syncs the Watchlist, sees it is missing from your *real* libraries, and sends the request to Radarr/Sonarr to download.

#### C. The Cleanup Flow (Tautulli Triggered)

1. **Import:** Sonarr imports the real file into `/media/real_shows`.
2. **Trigger:** Plex scans the real library. Tautulli detects the "Recently Added" event and fires the `cleanup_dummy.py` script.
3. **Wipe:** The script searches the `discover_shows` library for the matching title, permanently deletes the dummy folder from the hard drive, triggers a library scan, and surgically empties the discovery library's trash. The poster vanishes from your Smart Collections.

---

### Phase 3: Custom Scripts and Integration Points

You need two Python scripts to run this engine. Ensure you run `pip install requests plexapi` in your Python environment.

#### Script 1: The Master Ingestion Engine (`discovery_ingest.py`)

This script handles fetching from TMDB and Trakt, creating the files, and applying the labels so Kometa can build the collections. Set this to run nightly via Cron.

```python
import os
import shutil
import re
import requests
import time
from plexapi.server import PlexServer

# --- CONFIGURATION ---
TMDB_API_KEY = 'YOUR_TMDB_API_KEY'
TRAKT_CLIENT_ID = 'YOUR_TRAKT_CLIENT_ID'
PLEX_URL = 'http://localhost:32400'
PLEX_TOKEN = 'YOUR_PLEX_TOKEN'

TEMPLATE_FILE = '/scripts/dummy_template/dummy.mkv'
DISCOVER_MOVIES_PATH = '/media/discover_movies'
DISCOVER_SHOWS_PATH = '/media/discover_shows'
REAL_MOVIES_PATH = '/media/real_movies'
REAL_SHOWS_PATH = '/media/real_shows'

# Providers: Netflix(8), Hulu(15), Apple TV+(350), Max(384)
STREAMING_PROVIDERS = {'8': 'Discover_Netflix', '15': 'Discover_Hulu', '350': 'Discover_AppleTV', '384': 'Discover_Max'}
TRAKT_LISTS = ['recommendations-movies', 'recommendations-shows']

# --- DICTIONARY TO STORE PLEX LABELS FOR LATER TAGGING ---
items_to_tag = []

def sanitize_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", str(title)).strip()

def create_dummy(title, year, media_type, labels):
    if not year or year == 'Unknown': return
    folder_name = f"{sanitize_filename(title)} ({year})"
    
    if media_type in ['movie', 'movies']:
        if os.path.exists(os.path.join(REAL_MOVIES_PATH, folder_name)) or os.path.exists(os.path.join(DISCOVER_MOVIES_PATH, folder_name)):
            return
        target_dir = os.path.join(DISCOVER_MOVIES_PATH, folder_name)
        os.makedirs(target_dir, exist_ok=True)
        shutil.copyfile(TEMPLATE_FILE, os.path.join(target_dir, f"{folder_name}.mkv"))
        items_to_tag.append({'title': title, 'lib': 'Discover Movies', 'labels': labels, 'type': 'movie'})

    elif media_type in ['show', 'shows', 'tv']:
        if os.path.exists(os.path.join(REAL_SHOWS_PATH, folder_name)) or os.path.exists(os.path.join(DISCOVER_SHOWS_PATH, folder_name)):
            return
        target_dir = os.path.join(DISCOVER_SHOWS_PATH, folder_name, "Season 01")
        os.makedirs(target_dir, exist_ok=True)
        shutil.copyfile(TEMPLATE_FILE, os.path.join(target_dir, f"{folder_name} - S01E01.mkv"))
        items_to_tag.append({'title': title, 'lib': 'Discover Shows', 'labels': labels, 'type': 'show'})

def fetch_tmdb_streaming():
    print("Fetching TMDB Streaming Data (Depth: 100 per provider)...")
    for provider_id, label in STREAMING_PROVIDERS.items():
        for page in range(1, 6): # Pages 1-5 (20 items per page = 100 deep)
            for m_type in ['movie', 'tv']:
                url = f"https://api.themoviedb.org/3/discover/{m_type}?api_key={TMDB_API_KEY}&watch_region=US&with_watch_providers={provider_id}&sort_by=popularity.desc&page={page}"
                try:
                    results = requests.get(url).json().get('results', [])
                    for item in results:
                        title = item.get('title') if m_type == 'movie' else item.get('name')
                        year = item.get('release_date', '')[:4] if m_type == 'movie' else item.get('first_air_date', '')[:4]
                        
                        # Apply provider label and genre mapping (simplified here for space)
                        labels = [label, 'Discover_All']
                        create_dummy(title, year, m_type, labels)
                except Exception as e:
                    print(f"TMDB Error: {e}")
                time.sleep(0.5)

def fetch_trakt_recommendations():
    print("Fetching Trakt/Couchmoney Recommendations...")
    headers = {'Content-Type': 'application/json', 'trakt-api-version': '2', 'trakt-api-key': TRAKT_CLIENT_ID}
    for list_slug in TRAKT_LISTS:
        url = f"https://api.trakt.tv/users/couchmoney/lists/{list_slug}/items"
        try:
            results = requests.get(url, headers=headers).json()
            for item in results:
                m_type = item['type']
                media_data = item[m_type]
                create_dummy(media_data.get('title'), media_data.get('year'), m_type, ['Discover_Recs', 'Discover_All'])
        except Exception as e:
            print(f"Trakt Error: {e}")
        time.sleep(1)

def scan_and_tag_plex():
    if not items_to_tag: return
    print("Triggering Plex Scan...")
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    plex.library.section('Discover Movies').update()
    plex.library.section('Discover Shows').update()
    
    # Wait for Plex to finish scanning metadata
    while plex.isSessionsActive() or plex.library.section('Discover Movies').isUpdating or plex.library.section('Discover Shows').isUpdating:
        print("Waiting for Plex to finish scanning...")
        time.sleep(10)
        
    print("Scanning complete. Applying Labels...")
    for item in items_to_tag:
        try:
            results = plex.library.section(item['lib']).search(title=item['title'], libtype=item['type'])
            if results:
                for label in item['labels']:
                    results[0].addLabel(label)
                print(f"Tagged '{item['title']}' with {item['labels']}")
        except Exception as e:
            print(f"Failed to tag {item['title']}: {e}")

if __name__ == "__main__":
    fetch_tmdb_streaming()
    fetch_trakt_recommendations()
    scan_and_tag_plex()

```

#### Script 2: The Automated Cleanup (`cleanup_dummy.py`)

This script destroys the dummy file when Radarr/Sonarr successfully imports the real media.

```python
import os
import shutil
import sys
from plexapi.server import PlexServer

PLEX_URL = 'http://localhost:32400'
PLEX_TOKEN = 'YOUR_PLEX_TOKEN'

def main():
    if len(sys.argv) < 3: sys.exit(1)
    media_type = sys.argv[1] # 'movie' or 'show' passed from Tautulli
    title = sys.argv[2]      # Title passed from Tautulli
    
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    lib_name = 'Discover Shows' if media_type == 'show' else 'Discover Movies'
    discovery_lib = plex.library.section(lib_name)
    
    try:
        results = discovery_lib.search(title=title, libtype=media_type)
        if results:
            dummy_item = results[0] 
            folder_to_delete = dummy_item.locations[0]
            if os.path.exists(folder_to_delete):
                shutil.rmtree(folder_to_delete)
            discovery_lib.update()
            discovery_lib.emptyTrash()
            print(f"Cleaned up dummy for {title}")
    except Exception as e:
        print(f"Cleanup failed: {e}")

if __name__ == "__main__":
    main()

```

**Tautulli Trigger Configuration:**

* **Trigger:** Recently Added
* **Conditions:** `Library Name` is `Movies` OR `TV Shows` (Your real libraries).
* **Arguments:** `"{media_type}" "{title}"`

---

### Phase 4: Kometa Configuration

This is where the magic happens visually. Because our Python script applied labels directly in Plex, we do not need to dynamically rewrite YAML files. Kometa reads the labels and instantly constructs **Plex Smart Collections**.

Add the following to your Kometa metadata `.yml` file.

```yaml
templates:
  Discover Collection:
    smart_filter:
      all:
        label: <<label_name>>
    sort_title: <<sort_prefix>>_<<collection_name>>
    sync_mode: sync

collections:
  Recommended for Me:
    template: {name: Discover Collection, label_name: Discover_Recs, sort_prefix: 01}
    summary: Personalized Couchmoney recommendations based on your Trakt viewing history.
    
  Trending on Netflix:
    template: {name: Discover Collection, label_name: Discover_Netflix, sort_prefix: 02}
    
  Trending on Apple TV+:
    template: {name: Discover Collection, label_name: Discover_AppleTV, sort_prefix: 03}

  Trending on Max:
    template: {name: Discover Collection, label_name: Discover_Max, sort_prefix: 04}

  Trending on Hulu:
    template: {name: Discover Collection, label_name: Discover_Hulu, sort_prefix: 05}

# Add overlays to visually distinguish dummy files from real media
overlays:
  Request Needed:
    overlay:
      name: placeholder_icon # Drop a transparent PNG named this into your Kometa overlays folder
      group: topleft
      weight: 100
    plex_search:
      any:
        label: Discover_All

```

### The Result

You now have dynamic Smart Collections generated natively inside Plex by Kometa. They automatically expand as your Python script pulls new 100-deep lists from TMDB, they automatically shrink as Tautulli triggers your cleanup script upon actual acquisition, and they feature personalized Trakt data without paying a cent for VIP.


## Integration Guide

To ensure your placeholders are instantly and cleanly wiped off your server the second a real file arrives, we need to create a flawless chain of communication: **Sonarr/Radarr $\rightarrow$ Plex $\rightarrow$ Tautulli $\rightarrow$ Cleanup Script.**

While the term "webhook" is often used broadly, Tautulli actually uses a dedicated **Script Notification Agent** to run local Python scripts. This is much more secure and reliable than sending HTTP webhooks back and forth on your own server.

Here is the step-by-step implementation guide to wire this entire cleanup sequence together.

### Step 1: The Catalyst (Radarr & Sonarr Configuration)

For Tautulli to know a file was added, Plex has to scan it immediately. We need to ensure Radarr and Sonarr are telling Plex to do this the moment they finish downloading a file.

1. Open **Sonarr** and go to **Settings** $\rightarrow$ **Connect**.
2. Click the **+** button and select **Plex Media Server**.
3. Enter your Plex server IP and authenticate with your Plex account.
4. Under **Triggers**, ensure **On Import** and **On Upgrade** are checked.
5. Click **Save**.
6. Repeat this exact process in **Radarr**.

*Result: The second a real movie or show drops onto your hard drive, Radarr/Sonarr forces Plex to scan that specific folder.*

### Step 2: Prepare the Cleanup Script

Tautulli needs permission to execute your script.

1. Place the `cleanup_dummy.py` script we wrote earlier into a safe directory (e.g., `/scripts/tautulli_scripts/cleanup_dummy.py`).
2. If you are running on a Linux/macOS machine, make the script executable by running this command in your terminal:
`chmod +x /scripts/tautulli_scripts/cleanup_dummy.py`
3. Ensure the script has the correct `PLEX_URL` and `PLEX_TOKEN` hardcoded inside it.

### Step 3: Configure Tautulli for TV Shows (Sonarr Cleanup)

We will create two separate agents in Tautulli—one for shows and one for movies—to ensure the data is passed perfectly without complex conditional logic.

1. Open **Tautulli** and go to **Settings** $\rightarrow$ **Notification Agents**.
2. Click **Add a new notification agent** and select **Script**.
3. **Configuration Tab:**
* **Script Folder:** Enter the path to your folder (e.g., `/scripts/tautulli_scripts/`).
* **Script File:** Select `cleanup_dummy.py` from the dropdown.
* **Description:** Name it "Cleanup Dummy Shows".


4. **Triggers Tab:**
* Check the box for **Recently Added**.


5. **Conditions Tab:** * We only want this script to run when *real* media is added, so it doesn't trigger when your dummy script adds placeholders.
* Set Condition 1: `[ Library Name | is | Real Shows ]` *(Replace "Real Shows" with the exact name of your main TV library in Plex).*


6. **Arguments Tab:**
* Expand the **Recently Added** section.
* You need to pass the media type and the show title exactly as the script expects them: `media_type title`.
* Input exactly this: `show "{show_name}"`
* *Note: The quotation marks around `{show_name}` are mandatory so that shows with multiple words (like "Stranger Things") are treated as a single argument.*


7. Click **Save**.

### Step 4: Configure Tautulli for Movies (Radarr Cleanup)

Now, duplicate that setup for your movie library.

1. In **Tautulli**, go to **Settings** $\rightarrow$ **Notification Agents**.
2. Click **Add a new notification agent** $\rightarrow$ **Script**.
3. **Configuration Tab:** * Folder: `/scripts/tautulli_scripts/`
* File: `cleanup_dummy.py`
* Description: "Cleanup Dummy Movies"


4. **Triggers Tab:** * Check **Recently Added**.
5. **Conditions Tab:**
* `[ Library Name | is | Real Movies ]` *(Replace with the name of your main Movie library).*


6. **Arguments Tab:**
* Expand **Recently Added**.
* Input exactly this: `movie "{title}"`


7. Click **Save**.

### Step 5: The Final Architecture Test

To verify your fully custom discovery engine is bulletproof, run a manual test:

1. **The Dummy Phase:** Run your master `discovery_ingest.py` script manually in your terminal. Verify that a placeholder for a show is created, scanned into your "Discover Shows" library, and tagged correctly. Kometa should pick it up on its next run.
2. **The Request Phase:** Go into Plex, find that placeholder show, and add it to your Watchlist.
3. **The Interception:** Open Seerr and manually trigger a Plex Watchlist sync (or wait a few minutes). Ensure Seerr picks up the request and sends it to Sonarr.
4. **The Cleanup Phase:** Force Sonarr to search and download a small episode of that show.
5. **Watch the Magic:** * Watch Sonarr import the file.
* Check Tautulli's logs (Settings $\rightarrow$ View Logs). You should see an entry saying: `Tautulli Notifiers :: Script notification sent.`
* Check your Plex "Discover Shows" library. The placeholder poster should have completely vanished.

## Extras and tidbits

### 1. Integrating PlexTraktSync (The Watch-History Feeder)

**Where it fits in the plan:** PlexTraktSync sits at the very beginning of the data lifecycle. It runs silently in the background, watching your *real* Plex libraries. When you finish an episode or movie, it tells Trakt. Couchmoney reads that updated Trakt profile to generate your "Recommended for Me" list. Our nightly Python script then pulls that list to generate the dummy files.

**The Docker Compose Setup:**
Add this to your server's Docker ecosystem.

```yaml
services:
  plextraktsync:
    image: lscr.io/linuxserver/plextraktsync:latest
    container_name: plextraktsync
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./plextraktsync/config:/config
    restart: unless-stopped

```

**The Crucial Configuration Step:**
You must restrict PlexTraktSync so it *only* looks at your real media. If it scans your `discover_shows` library, it might accidentally sync 1-second dummy files to your Trakt history.

1. Spin up the container, then run the initial authentication wizard in your terminal: `docker exec -it plextraktsync plextraktsync`
2. Follow the prompts to authenticate with Trakt and Plex.
3. Open the generated `config.yml` inside your mapped `./plextraktsync/config` folder.
4. Set the `libraries` list to strictly target your real media:

```yaml
libraries:
  - Real Movies
  - Real Shows

```

Restart the container, and your data feeder is now running on permanent autopilot.

---

### 2. The Visual Home Page (Kometa Configuration)

Because our Python script does the heavy lifting of creating the dummy files and tagging them with Plex Labels (e.g., `Discover_Netflix`, `Coming_Soon`), Kometa's job is incredibly lightweight. It simply scoops up those labels, builds Smart Collections, and uses `visible_home: true` to pin them as beautiful horizontal rows on your Plex Home Screen.

**No `add_missing` flags are used here**, guaranteeing zero mass-downloading.

Save this as your `discovery_ui.yml` (and point your main Kometa `config.yml` to it):

```yaml
templates:
  discovery_row:
    smart_filter:
      all:
        label: <<label_name>>
        # Acts as a secondary failsafe to hide things you've already watched
        user_watched: false 
    sort_title: <<sort_prefix>>_<<collection_name>>
    sync_mode: sync
    # THIS is the magic flag that pins the row to your Plex Home Screen
    visible_home: true 
    # Optional: Limits the row length so the UI remains snappy
    limit: 40 

collections:
  Coming Soon (Requested):
    template: {name: discovery_row, label_name: Coming_Soon, sort_prefix: 00}
    summary: Media currently queued in Radarr and Sonarr awaiting release or download.

  Recommended for Me:
    template: {name: discovery_row, label_name: Discover_Recs, sort_prefix: 01}
    summary: Personalized Couchmoney recommendations based on your watch history.
    
  Trending on Netflix:
    template: {name: discovery_row, label_name: Discover_Netflix, sort_prefix: 02}
    
  Trending on Apple TV+:
    template: {name: discovery_row, label_name: Discover_AppleTV, sort_prefix: 03}

  Trending on Max:
    template: {name: discovery_row, label_name: Discover_Max, sort_prefix: 04}

  Trending on Hulu:
    template: {name: discovery_row, label_name: Discover_Hulu, sort_prefix: 05}

overlays:
  # Adds a visual indicator to the poster so you know it's a dummy file
  Request Needed Badge:
    overlay:
      name: request_needed_icon # Ensure a transparent PNG with this name is in your Kometa overlays folder
      group: topleft
      weight: 100
    plex_search:
      any:
        # Applies this badge to EVERYTHING tagged by our ingestion script
        label: Discover_All 

```

### How the Final UI Looks and Acts

When you open Plex on your TV, you won't have to navigate to an obscure "Collections" tab. You will see gorgeous, Netflix-style rows right on your Home screen: "Recommended for Me," "Trending on Apple TV+," etc.

Every poster in those rows will have a clean little "Request Needed" badge in the corner. You simply click into one, hit the "Add to Watchlist" button, and Seerr instantly handles the rest in the background, while Tautulli cleans up the dummy file later.