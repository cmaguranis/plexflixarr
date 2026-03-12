# Exclude Guide

What services to configure to exclude the discover libraries.

### 1. Overseerr (CRITICAL)

* **The Danger:** If Overseerr can see your Discover libraries, it will scan the `dummy.mkv` files and mark the media as **"Available"**. It will completely disable the "Request" button, effectively breaking your entire pipeline.
* **How to Exclude:**
1. Go to Overseerr -> **Settings** -> **Plex**.
2. Scroll down to your synced libraries.
3. Ensure your `Discover Movies` and `Discover Shows` libraries are completely **unchecked**. Overseerr should only sync your real libraries.


### 2. PlexTraktSync / PlexAniSync / CrossWatch (CRITICAL)

* **The Danger:** These tools catalog what you own and what you've watched. If they scan your Discover folders, they will report back to Trakt/AniList/Simkl that you have "collected" hundreds of unreleased shows and trending movies. It will permanently pollute your profile data and destroy the algorithm we are relying on for Couchmoney.
* **How to Exclude:**
* You must use an **allowlist** in their configuration files, rather than a blocklist.
* In your `plextraktsync/config.yml`, ensure the `libraries` section explicitly names only your real ones:
```yaml
libraries:
  - Real Movies
  - Real Shows
  - Real Anime

```

* If you use PlexAniSync or CrossWatch, configure their library settings to match.


### 3. Tautulli (Highly Recommended)

* **The Danger:** Tautulli tracks your server statistics. If you don't exclude the Discover libraries, your Tautulli homepage will be flooded with "Added 100 new movies" every single night when your cron job runs. It will completely skew your server metrics. Furthermore, you don't want your Cleanup Script triggering on the wrong library.
* **How to Exclude:**
1. **For Stats/Dashboards:** Go to Tautulli -> **Settings** -> **Homepage**. Under *Recently Added*, uncheck the Discover libraries. Go to **Settings** -> **Libraries** and uncheck the Discover libraries from tracking if you don't want them in your history at all.
2. **For the Cleanup Webhook:** As we mapped out earlier, ensure the *Conditions* tab of your Notification Agent explicitly states: `[ Library Name | is | Real Shows ]`.

### 4. Radarr & Sonarr (Structural Exclusion)

* **The Danger:** Radarr and Sonarr don't "scan" Plex libraries in the traditional sense, but they *do* look at root folders and can import Plex Watchlists directly. If they try to manage your dummy files, they will overwrite them or get confused by the 1-second file size and aggressively try to "upgrade" them.
* **How to Exclude:**
1. **Root Folders:** In Radarr/Sonarr -> **Settings** -> **Media Management**, ensure `/media/discover_movies` and `/media/discover_shows` are **never** added as root folders.
2. **Plex Lists:** If you have any Connections set up in Settings -> Import Lists to pull your Plex Watchlist, make sure it is configured to drop media into your `/media/real_media` paths *only*.

### 5. Plex Itself (UI Exclusion)

* **The Danger:** If you don't isolate the Discover libraries inside Plex, your home screen's global "Recently Added" row will be overwhelmed by dummy posters every morning, burying the actual, real media you just downloaded.
* **How to Exclude:**
1. In Plex, hover over the `Discover Movies` library on the left sidebar, click the three dots, and go to **Manage Library** -> **Edit**.
2. Go to the **Advanced** tab.
3. Uncheck **"Include in home screen"** (or "Include in dashboard").
4. Uncheck **"Include in global search"** (optional, but recommended so if you search for a movie, you don't get two identical results—one real, one fake).

### The Only Exception: Kometa

Kometa is the *only* third-party service in your entire ecosystem that is allowed to look at your Discover libraries. It is the sole reason they exist.

By applying these blindfolds across your stack, your server will operate flawlessly: Overseerr handles the requests, your sync tools build your algorithms, Radarr/Sonarr handle the files, and Kometa orchestrates the grand illusion.