You are reading my mind. Using a template is the absolute best practice here—it drastically reduces the size of your YAML file and makes adding future services (like Disney+ or Max) take about three seconds.

And your question about **Trending, Genres, etc.** brings us to the absolute best part of the Walled Garden setup.

Here is how you handle the templates, and why your genres and trending collections are about to become completely effortless.

### 1. The Kometa Template

Kometa allows you to define a `templates` block at the top of your YAML file. You use placeholder variables (like `<<service>>`) that get filled in when you call the template under your `collections` block.

```yaml
templates:
  Walled Garden:
    sync_mode: sync
    plex_search:
      any:
        label: <<trigger_label>>
    label:
      - hide_streaming
      - <<vip_label>>
    item_label:
      - hide_streaming
      - <<vip_label>>
    summary: "Walled garden for <<service_name>>, fed by local pipeline."

collections:
  Netflix Content:
    template:
      name: Walled Garden
      trigger_label: pipeline_netflix
      vip_label: Network_Netflix
      service_name: Netflix

  Hulu Content:
    template:
      name: Walled Garden
      trigger_label: pipeline_hulu
      vip_label: Network_Hulu
      service_name: Hulu

```

Now, if you want to add Apple TV+ later, you just drop in five lines of code under `collections` and Kometa handles the rest.

---

### 2. The Magic of Genres and Trending (Smart Filtering)

Because you set up the Walled Gardens using Plex's core **Restrictions** (`Allow Labels` / `Exclude Labels`), you do not need to create separate "Netflix Action" or "Hulu Trending" collections.

**Plex will dynamically filter standard collections based on who is looking at them.**

If your pipeline feeds TMDB genres to your items, and you use Kometa to build a generic **"Trending Now"** or **"Action Movies"** Smart Collection, you don't need to put *any* blindfolds or VIP passes on that collection.

Here is what happens automatically when different users click on your single "Action Movies" collection:

* **The Family:** Opens "Action Movies" and sees *Die Hard*, *The Matrix*, etc. Plex automatically hides *Extraction* because it has the `hide_streaming` blindfold.
* **The Netflix Profile:** Opens the exact same "Action Movies" collection. Plex automatically hides *Die Hard* and *The Matrix* because they lack the VIP pass. The collection is instantly populated *only* with *Extraction* and other Netflix action films.
* **The Hulu Profile:** Opens the exact same "Action Movies" collection and sees only Hulu action films.

One Kometa collection magically becomes three perfectly tailored collections depending on whose Walled Garden it is being viewed from.

---

**Would you like me to show you the YAML block for setting up a dynamic "Trending" or "Action" Smart Collection so you can see how perfectly it pairs with this template?**