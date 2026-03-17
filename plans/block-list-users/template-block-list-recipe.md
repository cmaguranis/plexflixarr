Here is how we translate your "blindfold" logic into a Kometa recipe.

To make this work, we need Kometa to apply labels to **both the collection itself** (so the row doesn't show up on their home screen) **and the items inside it** (so they can't bypass the collection and find the show via search or other library tabs).

### The Logic Breakdown

Based on the restrictions you set up in Phase 1:

* **Netflix Content** gets tagged with `hide_streaming` (hides from Family) and `hide_hulu` (hides from Hulu profile).
* **Hulu Content** gets tagged with `hide_streaming` (hides from Family) and `hide_netflix` (hides from Netflix profile).

### The Kometa Configuration

You will add this to your metadata file (e.g., `tv.yml` or `movies.yml`). This example uses Plex's built-in `network` and `studio` tags, which is the easiest way to grab these without needing external lists like Trakt.

```yaml
collections:
  Netflix Content:
    plex_search:
      any:
        network: Netflix # Grabs TV shows aired on Netflix
        studio: Netflix  # Grabs Movies produced by Netflix
    label:
      - hide_streaming
      - hide_hulu
    item_label:
      - hide_streaming
      - hide_hulu
    summary: "Content available on Netflix."

  Hulu Content:
    plex_search:
      any:
        network: Hulu
        studio: Hulu
    label:
      - hide_streaming
      - hide_netflix
    item_label:
      - hide_streaming
      - hide_netflix
    summary: "Content available on Hulu."

```

### What these settings do:

* **`plex_search`**: This tells Kometa to look at your existing Plex library and dynamically gather anything where the Studio or Network matches Netflix/Hulu.
* **`label`**: This applies the blindfold tags to the **Collection container** itself.
* **`item_label`**: This is the magic bullet. It applies the blindfold tags to **every individual movie and show** inside the collection.

### A Quick Note on Movies

Plex's metadata for TV shows is usually rock-solid when it comes to the `network` tag (e.g., it almost always knows a show is from Netflix). However, movie `studio` tags can sometimes be messy depending on where Plex pulled the data from. If you find that Kometa is missing some Netflix or Hulu movies, you can easily swap the `plex_search` out for an external list, like an IMDb list or an MDBList of streaming exclusives.

---

**Would you like me to show you how to pull from a Trakt or MDBList instead, just in case Plex's built-in studio tags aren't catching all your movies?**