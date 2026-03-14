# Exclusion & Filtering Guide

plexflixarr applies several layers of filtering before a dummy file is created. All thresholds are controlled via `.env` — no code changes required.

---

## 1. Quality Gate (TMDB votes)

Every item fetched from TMDB must clear both thresholds to pass.

| Variable | Default | Description |
|----------|---------|-------------|
| `TMDB_MIN_VOTE_AVERAGE` | `6.0` | Minimum TMDB vote average (scale 0–10) |
| `TMDB_MIN_VOTE_COUNT` | `100` | Minimum number of votes — prevents obscure titles with a single 10/10 vote sneaking through |

Items from Trakt and AniList are **exempt** from the quality gate — they are personalised recommendations and are assumed relevant by nature.

**Examples:**
```env
# Stricter — only well-reviewed titles
TMDB_MIN_VOTE_AVERAGE=7.0
TMDB_MIN_VOTE_COUNT=500

# Looser — include newer releases before they accumulate votes
TMDB_MIN_VOTE_AVERAGE=5.5
TMDB_MIN_VOTE_COUNT=50
```

---

## 2. Language Filter

TMDB results include content from every region. By default plexflixarr excludes the following ISO 639-1 language codes:

```
hi  (Hindi)
ta  (Tamil)
te  (Telugu)
ml  (Malayalam)
kn  (Kannada)
bn  (Bengali)
mr  (Marathi)
```

Override the list in `.env`:

```env
# Remove all language filtering
EXCLUDED_LANGUAGES=[]

# Add Korean, keep defaults
EXCLUDED_LANGUAGES=["hi","ta","te","ml","kn","bn","mr","ko"]

# Only exclude Japanese (e.g. you have a separate anime workflow)
EXCLUDED_LANGUAGES=["ja"]
```

Language filtering applies to TMDB results only. Trakt and AniList items are **not** filtered by language.

---

## 3. Duplicate Suppression (Real Library Check)

Before creating a dummy, each candidate is searched in your real Plex libraries. If it already exists there, no dummy is created and the item is silently skipped.

| Variable | Default | Description |
|----------|---------|-------------|
| `REAL_MOVIES_LIBS` | `["Movies","Anime Movies"]` | Plex library names to search for existing movies |
| `REAL_SHOWS_LIBS` | `["TV Shows","Anime TV"]` | Plex library names to search for existing shows |

The names must match your Plex library names exactly (case-sensitive).

```env
REAL_MOVIES_LIBS=["Movies","Anime Movies","4K Movies"]
REAL_SHOWS_LIBS=["TV Shows","Anime TV","Documentary"]
```

You can also trigger a manual dedupe pass at any time — useful after a bulk import:

```bash
curl -s -X POST http://localhost:8742/dummy/dedupe
```

---

## 4. Streaming Providers

Controls which streaming services are fetched from TMDB and which Plex label each maps to. The key is the [JustWatch provider ID](https://www.justwatch.com/) as used by TMDB.

Default providers:

| Provider ID | Service | Plex Label |
|-------------|---------|------------|
| `8` | Netflix | `Discover_Netflix` |
| `15` | Hulu | `Discover_Hulu` |
| `350` | Apple TV+ | `Discover_AppleTV` |
| `384` | Max | `Discover_Max` |
| `526` | AMC+ | `Discover_AMC` |
| `283` | Crunchyroll | `Discover_Crunchyroll` |
| `337` | Disney+ | `Discover_Disney` |
| `80` | Adult Swim | `Discover_AdultSwim` |

To add or remove providers, override `STREAMING_PROVIDERS` in `.env` as a JSON object:

```env
STREAMING_PROVIDERS={"8":"Discover_Netflix","337":"Discover_Disney","9":"Discover_Prime"}
```

Provider IDs can be found by browsing TMDB's `/watch/providers` endpoint or inspecting JustWatch URLs.

---

## 5. Genre Labels

TMDB genre IDs are mapped to additional Plex labels applied alongside the source label. An item can carry multiple genre labels (e.g. `Discover_Action` and `Discover_SciFi`).

Default genre map:

| Genre ID | Genre | Plex Label |
|----------|-------|------------|
| `28` | Action | `Discover_Action` |
| `35` | Comedy | `Discover_Comedy` |
| `18` | Drama | `Discover_Drama` |
| `27` | Horror | `Discover_Horror` |
| `878` | Science Fiction | `Discover_SciFi` |
| `10749` | Romance | `Discover_Romance` |
| `16` | Animation | `Discover_Animation` |
| `99` | Documentary | `Discover_Documentary` |

Genre IDs are documented on the [TMDB forum](https://www.themoviedb.org/talk/5daf6eb0ae36680011d7e6ee). Override in `.env`:

```env
DISCOVER_GENRES={"28":"Discover_Action","53":"Discover_Thriller","10749":"Discover_Romance"}
```

Genre labels apply to TMDB items only. Trakt and AniList items receive their source label (`Discover_Recs`, `Discover_Anime`) but not genre labels.

---

## 6. Volume / Breadth

| Variable | Default | Description |
|----------|---------|-------------|
| `PAGES_PER_PROVIDER` | `5` | TMDB pages fetched per provider per media type. Each page contains 20 items, so the default yields up to 100 candidates per provider before filtering. |

Increase to cast a wider net; decrease for a tighter, higher-quality list.
