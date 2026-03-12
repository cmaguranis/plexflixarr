I want to setup kometa https://kometa.wiki/en/latest/kometa/install/images/ in my home server. i have created an empty directory @kometa-config to store the configuration yaml for my service as well as a docker compose file with the correct configurations. The output of this plan should be the necessary configuration yaml and docker compose yaml files for setting it up given the information below. research and validate this approach works.

---

## Research Findings & Technical Constraints

These findings were validated during implementation planning. They override any conflicting claims in the sections below.

### Hard Constraints

**Kometa is a library-management tool, not a discovery platform.** It can only operate on items already present in the local Plex library. Collections are always subsets of local content. There is no "virtual item," "Discover builder," or streaming-source mode that bypasses this. Any suggestion to the contrary (including AI-generated YAML examples using `<<days_ago(365)>>` or "Discover builders") is incorrect and not in the Kometa codebase.

**The workaround is Radarr/Sonarr auto-add.** Kometa supports `radarr_add_missing: true` and `sonarr_add_missing: true` on any collection. When enabled, items from the source lists (MDBList, Trakt) that are not in the library are automatically queued in Radarr/Sonarr. Once acquired, they appear in Plex and Kometa includes them in collections on the next run. This is the assumed mechanism for "Coming Soon" and discovery rows throughout this document.

**Plex Discover (native) is the zero-download alternative.** If streaming services are configured as Sources in Plex settings, the Discover tab already provides catalog browsing and "where to watch" results without Kometa or downloading anything. This document does not replicate that; Kometa's role is to organize the *local* library.

### Known False Assumptions in Source Material

The following assumptions in the original prompt fragments are incorrect and are annotated inline below:

1. `mdblist_list` cannot be nested inside `smart_filter.all` — it is a top-level builder, not a filter condition.
2. The Trakt community list URLs (e.g., `users/official/lists/winter-2026-anime`, `users/movist/lists/netflix-korean-content`, `users/japanese-drama/lists/top-rated`) are AI-generated and do not exist. They must be replaced with real, verified list URLs before use.
3. `type: network` dynamic collections depend on Plex network metadata matching the exact streaming service name. This is unreliable across metadata agents and requires testing per library.
4. MDBList's "Exclude Watched" (via Trakt OAuth in MDBList) and Kometa's `user_watched: false` are not redundant — they operate at different stages — but the original text misrepresents them as a single mechanism.
5. `plex_search` and `mdblist_list` used as sibling keys inside a `template:` block is syntactically incorrect; they must be top-level collection builders.
6. "Coming Soon" items will not appear in discovery rows unless Radarr/Sonarr has queued and acquired them. The rows will be empty without the `radarr_add_missing`/`sonarr_add_missing` workaround.

---

## prompt

### System Prompt & Architecture Specification for Coding Agent

**Objective**
Generate production-ready Kometa (Plex Meta Manager) YAML configuration files to create a personalized, Netflix-style discovery interface on a Plex server. The system must automate categorized recommendations, filter by specific streaming services, exclude watched content, and operate without paid API subscriptions (e.g., Trakt VIP or Simkl VIP).

**Infrastructure & Data Flow**

1. **PlexTraktSync (Docker):** Runs on an OpenMediaVault server, syncing local Plex watch history to a free Trakt account to maintain accurate "watched" states.
2. **MDBList (Free Tier):** Acts as the primary catalog filter. Generates dynamic lists restricted to specific streaming providers and baseline popularity thresholds.
3. **Trakt (Free Tier):** Provides community-curated lists for niche media (Asian dramas, anime) and global trending/anticipated metrics.
4. **Radarr/Sonarr:** Bridges the gap between external lists and the local library. Kometa's `radarr_add_missing`/`sonarr_add_missing` flags queue items from MDBList/Trakt into Radarr/Sonarr for acquisition. Once downloaded, Kometa organizes them into discovery rows.
5. **Kometa:** The execution engine. It ingests MDBList and Trakt URLs, applies local Plex Smart Filters (to exclude watched history), and generates Smart Collections pinned to the Plex Home screen.

**Catalog Requirements**

* **Target Services:** Netflix, Hulu, Apple TV+, Crunchyroll.
* **Content Types:** Western Movies/TV, Anime, Japanese Dramas, Korean Dramas.
* **Display Format:** Categorized horizontal rows (e.g., Action, Sci-Fi) and dedicated rows for "Coming Soon" and niche Asian media.

**Implementation Specifications for Kometa YAML**

**1. Templates & DRY Logic**

* Utilize Kometa `templates` to define the base logic for a discovery row.
* Base templates must utilize `smart_filter` or `plex_search` to ensure collections act as Plex Smart Collections. This satisfies the user requirement for "infinite scrolling" by allowing the row header to be clicked to view the full, paginated list in Plex.
* Base templates must include `user_watched: false` to ensure recommendations are strictly personalized to unwatched content.

**2. Dynamic Genre Groupings**

* Use `dynamic_collections` with `type: genre` to automatically split a master MDBList into separate, genre-specific rows.
* Restrict the generated rows using the `include` parameter to prevent UI clutter (e.g., only generate Action, Sci-Fi, Animation, Mystery, Horror, Adventure).

**3. Dedicated Static Rows**

* Define explicit collections for "Coming Soon", "Trending Anime", and "New K-Dramas".
* "Coming Soon" intersects an MDBList (filtered for upcoming dates on the target services) with Trakt `anticipated` sorting, and uses `radarr_add_missing`/`sonarr_add_missing` to pre-populate the library with anticipated titles.
* Asian media rows rely on specific community Trakt lists (URLs must be verified manually before use — see constraint #2 above).

**Coding Standards & Constraints (STRICT)**

* **Indentation:** Use exactly 2 spaces for all YAML indentation. Do not use tabs.
* **Comments:** Comments must be production-ready. Explain the *why* behind a configuration block, not the *what*. Keep language concise.
* **Emojis:** Do not output any emojis in the code, comments, or documentation.
* **Variables:** Use standard Kometa template variables (e.g., `<<key_name>>`) for dynamic naming.

---

**Reference Example for the Agent (style guide only — see constraint annotations):**

```yaml
# CORRECT: mdblist_list and smart_filter are separate top-level builders.
# Using mdblist_list as a filter condition inside smart_filter.all is invalid syntax.
templates:
  discovery_row:
    # mdblist_list populates the collection item set
    mdblist_list: <<list_url>>
    # smart_filter restricts it to unwatched library items only
    smart_filter:
      all:
        genre: <<genre_name>>
        user_watched: false
    visible_home: true
    sync_mode: sync
    limit: 40
    sort_by: release.desc
    # Queues items from the list that are not yet in the library
    radarr_add_missing: true

dynamic_collections:
  Service_Genres:
    type: genre
    include: [Action, Sci-Fi, Animation, Mystery, Horror]
    template: discovery_row
    template_variables:
      list_url: https://mdblist.com/lists/YOUR_USERNAME/my-streaming-services
      genre_name: <<key_name>>

collections:
  Anticipated Releases:
    # MDBList scopes to your subscribed services; trakt_chart sorts by community hype
    mdblist_list: https://mdblist.com/lists/YOUR_USERNAME/coming-soon-list
    trakt_chart: anticipated
    sync_mode: sync
    visible_home: true
    collection_order: custom
    limit: 30
    radarr_add_missing: true
    sonarr_add_missing: true
```

---

## Implementation Architecture

### Phase 1: Data Bridge (PlexTraktSync)

The linuxserver image includes an internal scheduler; no host-level cron is required after initial setup.

**Docker Compose:**

```yaml
services:
  plextraktsync:
    image: lscr.io/linuxserver/plextraktsync:latest
    container_name: plextraktsync
    environment:
      # Aligns container file ownership with standard OpenMediaVault user permissions
      - PUID=1000
      - PGID=100
      # Localizes the internal cron scheduler for accurate logging
      - TZ=America/New_York
    volumes:
      # Persists Trakt OAuth tokens and YAML configurations across updates
      - ./plextraktsync/config:/config
    restart: unless-stopped
```

**Initial authentication (run once):**

```bash
# Initiates the primary CLI wizard to generate the .env and .pytrakt.json files
docker exec -it plextraktsync plextraktsync
```

The wizard will provide a Trakt URL and PIN. Complete the browser authorization, then authenticate with Plex when prompted. After this, the container runs unattended.

**`config.yml` modifications (inside the mapped `./plextraktsync/config` volume):**

```yaml
# Explicitly defining libraries ensures only curated media impacts your Trakt history.
# Inclusion list is more resilient than exclusion in home labs where new pools appear frequently.
libraries:
  - Movies
  - TV Shows
  - Anime
  - K-Dramas

# Secondary firewall against metadata pollution from non-commercial content.
excluded-libraries:
  - Home Videos
  - Security Cam
  - Personal Backups
  - NAS Archive

# Bidirectional sync ensures Kometa's user_watched filter and MDBList's Exclude Watched
# both have accurate, up-to-date data to work from.
sync:
  plex_to_trakt:
    collection: true
    ratings: true
    watched_status: true
  trakt_to_plex:
    ratings: true
    watched_status: true
    playback_status: true
```

Library names are case-sensitive and must match the Plex sidebar exactly. After editing, restart: `docker compose restart plextraktsync`.

---

### Phase 2: Catalog Filters (MDBList)

MDBList scopes Kometa's source data to your subscribed streaming services. Create two lists at mdblist.com:

**List 1 — "My Streaming Services" (genre rows)**
* Services: Netflix, Hulu, Apple TV+, Crunchyroll
* Quality: IMDb score > 6.0
* Connect your Trakt account and enable "Exclude Watched" — this filters at the source before Kometa's `user_watched: false` applies at the Plex layer

**List 2 — "Coming Soon on My Services" (anticipated row)**
* Services: Netflix, Hulu, Apple TV+, Crunchyroll
* Release status: Upcoming / In Production
* Release date: after today
* Popularity threshold: set to avoid low-signal indie titles

Copy both list URLs. You will need them in the Kometa configuration.

---

### Phase 3: UI Engine (Kometa)

Kometa reads the MDBList and Trakt sources, intersects them with local library content (filtering out watched items), and pins Smart Collections to the Plex home screen. Items on the source lists that are not yet in the library are queued in Radarr/Sonarr via `radarr_add_missing`/`sonarr_add_missing`.

**MDBList API key goes in `config.yml`:**

```yaml
mdblist:
  apikey: YOUR_MDBLIST_API_KEY
  cache_expiration: 1
```

**Genre rows (`Movies.yml` / `TV Shows.yml`):**

```yaml
templates:
  streaming_genre_row:
    # mdblist_list populates the item set from your scoped streaming catalog
    mdblist_list: https://mdblist.com/lists/YOUR_USERNAME/my-streaming-services
    # smart_filter narrows to this genre and removes already-watched items
    smart_filter:
      all:
        genre: <<genre_name>>
        user_watched: false
    visible_home: true
    sync_mode: sync
    sort_by: release.desc
    limit: 40
    # Items on the MDBList not yet in the library are queued for acquisition
    radarr_add_missing: true

dynamic_collections:
  Streaming Discovery:
    type: genre
    include: [Action, Sci-Fi, Animation, Mystery, Horror, Adventure]
    title_format: "<<key_name>> on My Services"
    template: streaming_genre_row
    template_variables:
      genre_name: <<key_name>>
```

> ⚠ `type: network` was in the original draft for streaming service rows (e.g., "Trending on Netflix"). This depends on Plex network metadata matching the service name exactly, which varies by metadata agent. Validate against your actual library before using it.

**Asian media rows (`TV Shows.yml` or `Anime.yml`):**

> ⚠ The Trakt list URLs below are placeholders derived from AI-generated examples. They do not exist as written. Before using, search trakt.tv manually for active community lists that match these categories and replace the URLs.

```yaml
collections:
  # Replace the trakt_list URL with a verified community list for Korean content
  K-Drama Discovery:
    trakt_list: https://trakt.tv/users/VERIFIED_USER/lists/VERIFIED_K_DRAMA_LIST
    sync_mode: sync
    visible_home: true
    smart_filter:
      all:
        user_watched: false
    limit: 20
    summary: Korean titles from your streaming services.
    sonarr_add_missing: true

  # Replace the trakt_list URL with a verified seasonal anime list
  Current Season Anime:
    trakt_list: https://trakt.tv/users/VERIFIED_USER/lists/VERIFIED_ANIME_LIST
    sync_mode: sync
    visible_home: true
    smart_filter:
      all:
        user_watched: false
    limit: 30
    summary: Freshly airing anime currently available on streaming.
    sonarr_add_missing: true

  # Replace with a verified Japanese drama list
  Top Japanese Cinema & Dramas:
    trakt_list: https://trakt.tv/users/VERIFIED_USER/lists/VERIFIED_JDRAMA_LIST
    sync_mode: sync
    visible_home: true
    smart_filter:
      all:
        user_watched: false
    limit: 20
    sonarr_add_missing: true
```

**Coming Soon row:**

> ⚠ This row will be empty unless `radarr_add_missing`/`sonarr_add_missing` is enabled. Items with "Upcoming" or "In Production" status are not in the library by definition. The flags below are required for this row to populate.

```yaml
collections:
  Coming Soon to My Services:
    # MDBList scopes to your subscribed services and upcoming release dates
    mdblist_list: https://mdblist.com/lists/YOUR_USERNAME/coming-soon-list
    # Trakt anticipated sort surfaces the most community-hyped titles first
    trakt_chart: anticipated
    sync_mode: sync
    visible_home: true
    collection_order: custom
    limit: 30
    summary: Upcoming releases scheduled for your subscribed streaming services.
    radarr_add_missing: true
    sonarr_add_missing: true
```

---

### MDBList vs. Trakt: When to Use Each

| Use MDBList for... | Use Trakt for... |
| --- | --- |
| Service filtering: ensuring content is on Netflix/Hulu/etc. | Social discovery: what is trending or most anticipated globally |
| Technical filters: language (Japanese/Korean), year ranges, ratings | Niche curation: community-maintained lists for anime, K-dramas, J-dramas |
| Catalog scope: "everything on Crunchyroll" | Personalization: recommendations informed by PlexTraktSync watch history |

---

## documentation

- kometa: https://kometa.wiki
- PlexTraktSync: https://github.com/Taxel/PlexTraktSync?tab=readme-ov-file#docker-compose
- trakt api: https://trakt.docs.apiary.io/#reference/recommendations
- mdblist: https://mdblist.com
