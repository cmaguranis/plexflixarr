# plexflixarr

Custom streaming service discovery injection into Plex. Browse trending content from Netflix, Hulu, Apple TV+, and Max — filtered by quality ratings — directly as Plex home screen rows. Add something to your Watchlist, and Seerr downloads it. The dummy disappears automatically when the real file arrives.

---

## How It Works

```mermaid
%%{init: {'theme': 'dark'}}%%
flowchart LR
    TMDB["TMDB API"]
    Trakt["Trakt / Couchmoney"]
    MDB["Quality Gate\n(MDBList)"]
    Dummy["dummy .mkv"]
    Scan["Plex scan"]
    Label["Plex label"]

    TMDB --> MDB --> Dummy
    Trakt --> Dummy
    Dummy --> Scan --> Label

    Label --> SC["Smart Collections"]
    Label --> HSR["Home screen rows"]
    Label --> Badge["&quot;Request Needed&quot; badge"]

    Watchlist["User Watchlist"] --> Seerr
    Seerr --> SR["Sonarr / Radarr"]
    SR --> Real["real file imported"]
    Real --> Tautulli["Tautulli cleanup"]
    Tautulli --> Del["dummy deleted"]
    Tautulli --> Gone["poster vanishes"]
```

**Key constraint:** Kometa only organises items already in the Plex library. All content population is handled by the `ingest` script — Kometa never triggers downloads.

---

## Prerequisites

You need the following services running before plexflixarr can operate:

| Service | Role |
|---------|------|
| **Plex Media Server** | Hosts both your real and discovery libraries |
| **Sonarr** | Downloads and manages TV shows |
| **Radarr** | Downloads and manages movies |
| **Seerr** | Converts Plex Watchlist additions into Sonarr/Radarr requests |
| **Tautulli** | Watches Plex events and fires the cleanup script |
| **Kometa** | Reads Plex labels and builds Smart Collection rows (included in `docker-compose.yml`) |
| **PlexTraktSync** | Syncs your watch history to Trakt (included in `docker-compose.yml`) |

---

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys and media paths

# 3. Run the ingestion pipeline manually
uv run ingest

# 4. Trigger cleanup manually (normally called by Tautulli)
uv run cleanup show "Stranger Things"
uv run cleanup movie "Inception"
```

### Running via Docker

```bash
# Build and run ingestion once
docker compose run --rm plundarr

# Start Kometa + PlexTraktSync as persistent services
docker compose up -d kometa plextraktsync
```

### Scheduling Nightly Ingestion

Add to your host crontab (`crontab -e`):

```
0 2 * * * cd /path/to/plexflixarr && uv run ingest >> /var/log/plundarr.log 2>&1
```

---

## Setup

### 1. TMDB (The Movie Database)

**Purpose:** Fetches the top trending content per streaming service using JustWatch's backend data — free and unlimited.

1. Go to [themoviedb.org](https://www.themoviedb.org/) and create a free account.
2. Verify your email and log in.
3. Click your profile icon → **Settings** → **API** (left sidebar).
4. Click **Create** or **Request an API Key** → choose **Developer** (free).
5. Fill out the brief form (e.g. "Personal script to organise my home media server").
6. Copy the **API Key (v3 auth)**.

**Where it goes:** `TMDB_API_KEY` in `.env`.

---

### 2. Trakt.tv

**Purpose:** The central hub for your watch history. PlexTraktSync feeds viewing data into Trakt; the ingest script pulls personalised recommendations out via Couchmoney.

1. Go to [trakt.tv](https://trakt.tv/) and create a free account. Do not pay for VIP.
2. Click your profile icon → **Settings** → **Your API Apps** (bottom of left sidebar).
3. Click **New Application**.
   - **Name:** "Plex Discovery Engine" (or any name you like).
   - **Redirect URI:** `urn:ietf:wg:oauth:2.0:oob`
4. Click **Save App**.
5. Copy the **Client ID**.

**Where it goes:** `TRAKT_CLIENT_ID` in `.env`.

---

### 3. Couchmoney.tv

**Purpose:** Reads your Trakt watch history and generates a daily "Recommended for Me" list. The ingest script pulls this list to create personalised dummy files.

1. Go to [couchmoney.tv](https://couchmoney.tv/).
2. Click **Login with Trakt** and authorise the connection.
3. Couchmoney generates default lists (typically "TV Recommendations" and "Movie Recommendations").
4. Go to your Trakt profile → **Lists**. Find the Couchmoney lists and note their **slugs** (the URL-friendly name in the list URL, e.g. `recommendations-movies`, `recommendations-shows`).

The ingest script uses `recommendations-movies` and `recommendations-shows` by default. If your slugs differ, override in `src/clients/trakt_client.py` or pass them to `fetch_recommendations()`.

---

### 4. MDBList

**Purpose:** Quality gate. Every item fetched from TMDB is checked against MDBList's rating database (Trakt score and Rotten Tomatoes) before a dummy file is created. Free tier allows 1,000 lookups per day, which comfortably covers a nightly run.

1. Go to [mdblist.com](https://mdblist.com/) and create a free account.
2. Click your profile icon → **API Key** (or navigate to Settings → API).
3. Copy your API key.

**Where it goes:** `MDBLIST_API_KEY` in `.env`.

Thresholds (defaults: Trakt ≥ 70 or RT ≥ 60):
- `MDBLIST_MIN_TRAKT` — minimum Trakt score (0–100)
- `MDBLIST_MIN_RT` — minimum Rotten Tomatoes score (0–100)

---

### 5. Local Server Credentials

#### Plex Token

1. Open Plex Web and play any media item.
2. Click the `…` menu on the item → **Get Info** → **View XML**.
3. In the URL bar, find `X-Plex-Token=` — copy the value after the `=`.

**Where it goes:** `PLEX_TOKEN` in `.env`. Also update `kometa-config/config.yml` → `plex.token`.

#### Sonarr API Key

Sonarr → **Settings** → **General** → **Security** → API Key.

**Where it goes:** `SONARR_API_KEY` in `.env`.

#### Radarr API Key

Radarr → **Settings** → **General** → **Security** → API Key.

**Where it goes:** `RADARR_API_KEY` in `.env`.

---

### 6. Plex Library Setup

Create two new libraries to hold dummy files, isolated from your real media.

1. In Plex Web, click **More** → **+** (Add Library).
2. **Discover Movies:** Type = Movies, folder = your `DISCOVER_MOVIES_PATH` value (e.g. `/media/discover_movies`).
3. **Discover Shows:** Type = TV Shows, folder = your `DISCOVER_SHOWS_PATH` value (e.g. `/media/discover_shows`).
4. For both libraries, go to **Settings** → uncheck **Include library in dashboard** to prevent dummy files from appearing in Continue Watching or global Recently Added.

---

### 7. Seerr

Seerr must be blind to the discovery libraries so it treats Watchlist requests as genuinely missing media.

1. Open Seerr → **Settings** → **Plex**.
2. In the library list, **uncheck** both **Discover Movies** and **Discover Shows**.
3. Save.

---

### 8. Kometa

Kometa reads Plex labels applied by the ingest script and builds Smart Collections pinned to the Plex home screen.

1. Update `kometa-config/config.yml`:
   - Set `plex.url` to your Plex server address (e.g. `http://192.168.1.100:32400`).
   - Set `plex.token` to your Plex token.
2. **Overlay badge:** Replace the placeholder PNG at `kometa-config/assets/overlays/request_needed_icon.png` with a transparent PNG of your preferred "Request Needed" badge design.
3. Start Kometa via Docker:
   ```bash
   docker compose up -d kometa
   ```
4. Kometa will run once on startup (`KOMETA_RUN=true`). To schedule recurring runs, remove that env var and set `KOMETA_TIME` (e.g. `KOMETA_TIME=03:00`).

Collections defined in `kometa-config/discovery_ui.yml` will appear as horizontal rows on your Plex home screen after the first successful run.

---

### 9. PlexTraktSync

PlexTraktSync keeps Trakt's watch history in sync with Plex so Couchmoney generates accurate recommendations.

**Important:** restrict it to your **real** libraries only. If it scans the discovery libraries, 1-second dummy files will pollute your Trakt history.

1. Start the container:
   ```bash
   docker compose up -d plextraktsync
   ```
2. Run the one-time authentication wizard:
   ```bash
   docker exec -it plextraktsync plextraktsync
   ```
   Follow the prompts to authorise Trakt (browser PIN) and Plex.
3. Open `./plextraktsync/config/config.yml` and restrict to real libraries:
   ```yaml
   libraries:
     - Movies       # replace with your exact Plex library names
     - TV Shows
   ```
4. Restart the container:
   ```bash
   docker compose restart plextraktsync
   ```

---

### 10. Tautulli — Cleanup Trigger

Tautulli calls the `cleanup` script the moment a real file is imported into Plex, removing the corresponding dummy.

Create **two** Script Notification Agents — one for shows, one for movies.

**Agent 1 — TV Shows:**

1. Tautulli → **Settings** → **Notification Agents** → **Add a new notification agent** → **Script**.
2. **Configuration tab:**
   - Script Folder: directory containing your `cleanup` entry point (or a wrapper: `uv run cleanup`).
   - Script File: `cleanup` (or the wrapper script name).
   - Description: `Cleanup Dummy Shows`
3. **Triggers tab:** check **Recently Added**.
4. **Conditions tab:**
   - `Library Name` **is** `<your real TV library name>` (e.g. `TV Shows`)
   - This prevents the agent from firing when the ingest script adds dummy files.
5. **Arguments tab** → expand **Recently Added**:
   ```
   show "{show_name}"
   ```
   The quotes around `{show_name}` are mandatory for multi-word titles.
6. **Save**.

**Agent 2 — Movies:**

Repeat the above with:
- Description: `Cleanup Dummy Movies`
- Condition: `Library Name` **is** `<your real Movies library name>` (e.g. `Movies`)
- Arguments:
  ```
  movie "{title}"
  ```

---

### 11. Sonarr / Radarr — Plex Notification

Sonarr and Radarr must notify Plex immediately on import so Tautulli picks up the event.

1. **Sonarr** → **Settings** → **Connect** → **+** → **Plex Media Server**.
   - Enter your Plex server address and authenticate.
   - Enable **On Import** and **On Upgrade**.
   - Save.
2. Repeat in **Radarr**.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values before running.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PLEX_URL` | Yes | `http://localhost:32400` | Plex server base URL |
| `PLEX_TOKEN` | Yes | — | Plex authentication token |
| `TMDB_API_KEY` | Yes | — | TMDB v3 API key |
| `TRAKT_CLIENT_ID` | Yes | — | Trakt application Client ID |
| `MDBLIST_API_KEY` | Yes | — | MDBList API key (quality gate) |
| `MDBLIST_MIN_TRAKT` | No | `70` | Minimum Trakt score to pass |
| `MDBLIST_MIN_RT` | No | `60` | Minimum Rotten Tomatoes score to pass |
| `SONARR_BASEURL` | Yes | `http://localhost:8989` | Sonarr base URL |
| `SONARR_API_KEY` | Yes | — | Sonarr API key |
| `RADARR_BASEURL` | Yes | `http://localhost:7878` | Radarr base URL |
| `RADARR_API_KEY` | Yes | — | Radarr API key |
| `DISCOVER_MOVIES_PATH` | Yes | — | Absolute path to discovery movies folder |
| `DISCOVER_SHOWS_PATH` | Yes | — | Absolute path to discovery shows folder |
| `REAL_MOVIES_PATH` | Yes | — | Absolute path to real movies library folder |
| `REAL_SHOWS_PATH` | Yes | — | Absolute path to real shows library folder |
| `TEMPLATE_FILE` | No | `assets/dummy.mkv` | Path to 1-second dummy video |
| `PAGES_PER_PROVIDER` | No | `5` | TMDB pages per provider per type (20 items/page) |

---

## Project Structure

```
src/
  config.py               Pydantic settings (reads from .env)
  dummy.py                ffmpeg template generation, dummy file fs ops
  clients/
    plex_client.py        plexapi wrapper
    tmdb_client.py        TMDB /discover API
    mdblist_client.py     MDBList quality gate (Trakt / RT ratings)
    trakt_client.py       Trakt / Couchmoney recommendations
    sonarr_client.py      Sonarr API
    radarr_client.py      Radarr API
  jobs/
    ingestion.py          Nightly pipeline entry point
    cleanup.py            Tautulli-triggered cleanup entry point
    queue.py              SQLite job queue
    schedule.py           JSON-backed enable/disable flag
kometa-config/
  config.yml              Kometa: Plex connection + library mapping
  discovery_ui.yml        Kometa: Smart Collections + overlay badge
assets/
  dummy.mkv               Pre-generated 1-second dummy video template
```

---

## Development

```bash
uv run ruff check src/ tests/   # lint
uv run pytest                   # tests
```
