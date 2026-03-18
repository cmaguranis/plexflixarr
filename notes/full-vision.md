# Full Vision for Kometa collections

## Prompt

walk through the configuration and resulting output of this example:

collections:
- trending
- trending netflix
- trending hulu
- recently added
- action
- scifi
- romance

users:
dad, mom, netflix, hulu

dad sees:
- trending (not the specific trending netflix or hulu collections)
- recently added across all content
- action across all content
- scifi across all content

mom sees:
- trending (not the specific trending netflix or hulu collections)
- recently added across all content
- scifi across all content
- romance across all content

netflix sees:
- trending netflix
- recently added with netflix labeled items only
- action with netflix labeled items only
- scifi with netflix labeled items only
- romance with netflix labeled items only

hulu sees:
- trending hulu
- recently added with hulu labeled items only
- action with hulu labeled items only
- scifi with hulu labeled items only
- romance with hulu labeled items only

## Walkthrough

This is the exact scenario where the hybrid whitelist/blocklist system shines. To make this work perfectly, we just need to introduce two new "blindfold" labels to hide specific genres from Dad and Mom.

Here is the complete walk-through of how to configure this in Plex and Kometa, and exactly what happens when each user logs in.

### Phase 1: The Plex User Restrictions (The Rules)

In Plex (under **Users & Sharing > Restrictions**), you will set up the profiles like this:

* **Dad**
* **Allow Labels:** *(Leave blank)* * **Exclude Labels:** `hide_streaming`, `hide_dad` *(This new label will hide Romance).*


* **Mom**
* **Allow Labels:** *(Leave blank)*
* **Exclude Labels:** `hide_streaming`, `hide_mom` *(This new label will hide Action).*


* **Netflix**
* **Allow Labels:** `Network_Netflix` *(The VIP pass).*
* **Exclude Labels:** *(Leave blank)*


* **Hulu**
* **Allow Labels:** `Network_Hulu` *(The VIP pass).*
* **Exclude Labels:** *(Leave blank)*



---

### Phase 2: The Kometa Configuration (The Execution)

*Note: This assumes your ingestion pipeline is still tagging the underlying individual movies/shows with `Network_Netflix` and `Network_Hulu` so Plex knows who is allowed to watch what.*

Here is the exact YAML to build those seven collections:

```yaml
collections:
  # 1. The General Trending Collection (For Family Only)
  Trending All:
    trakt_trending: 30
    label: [] # Left blank! Meta-users can't see this because they lack a VIP pass.

  # 2. Provider-Specific Trending Collections
  Trending Netflix:
    trakt_trending: 30
    smart_filter:
      all:
        label: Network_Netflix
    label:
      - hide_streaming    # Hides from Dad and Mom
      - Network_Netflix   # Allows Netflix profile to see the row

  Trending Hulu:
    trakt_trending: 30
    smart_filter:
      all:
        label: Network_Hulu
    label:
      - hide_streaming    # Hides from Dad and Mom
      - Network_Hulu      # Allows Hulu profile to see the row

  # 3. Shared Collections (Dynamically filtered by Plex)
  Recently Added:
    smart_filter:
      all:
        added: -30
    sort_by: added.desc
    label:
      - Network_Netflix   # Makes row visible to Netflix
      - Network_Hulu      # Makes row visible to Hulu
      # Dad and Mom see this automatically because it has no 'hide' labels.

  Action:
    smart_filter:
      all:
        genre: Action
    label:
      - Network_Netflix
      - Network_Hulu
      - hide_mom          # Mom's blindfold for this specific collection

  Sci-Fi:
    smart_filter:
      all:
        genre: Science Fiction
    label:
      - Network_Netflix
      - Network_Hulu
      # No blindfolds. Dad and Mom both see it.

  Romance:
    smart_filter:
      all:
        genre: Romance
    label:
      - Network_Netflix
      - Network_Hulu
      - hide_dad          # Dad's blindfold for this specific collection

```

---

### Phase 3: The Resulting Output (The Magic)

Here is exactly what happens when each person opens the Plex app on the living room TV.

#### 🎬 Dad logs in...

Plex checks his profile. He has no Whitelists, but he is wearing the `hide_streaming` and `hide_dad` blindfolds.

* **Trending All:** Visible. It has no restriction tags. (He sees a mix of Local, Netflix, and Hulu trending items).
* **Trending Netflix / Hulu:** Hidden. (`hide_streaming` blocks him).
* **Recently Added:** Visible.
* **Action:** Visible.
* **Sci-Fi:** Visible.
* **Romance:** Hidden. (`hide_dad` blocks him).

#### 🍿 Mom logs in...

Plex checks her profile. She has no Whitelists, but she is wearing the `hide_streaming` and `hide_mom` blindfolds.

* **Trending All:** Visible. (She sees a mix of Local, Netflix, and Hulu trending items).
* **Trending Netflix / Hulu:** Hidden. (`hide_streaming` blocks her).
* **Recently Added:** Visible.
* **Action:** Hidden. (`hide_mom` blocks her).
* **Sci-Fi:** Visible.
* **Romance:** Visible.

#### 🟥 The Netflix Profile logs in...

Plex checks the profile. It is a Walled Garden. The screen is blank except for collections wearing the `Network_Netflix` label.

* **Trending All:** Hidden. (It lacks the `Network_Netflix` VIP pass).
* **Trending Netflix:** Visible.
* **Trending Hulu:** Hidden. (Lacks the VIP pass).
* **Recently Added / Action / Sci-Fi / Romance:** All of these rows are visible because Kometa stamped them with the `Network_Netflix` label.
* *The Magic Trick:* When the Netflix profile clicks into the "Sci-Fi" collection, Plex's internal logic takes over. It completely hides your local copies of *Dune* or *Star Wars*, and only shows Netflix Originals like *Altered Carbon*, because those are the only items in your library wearing the `Network_Netflix` item label.

#### 🟩 The Hulu Profile logs in...

Plex checks the profile. The screen is blank except for collections wearing the `Network_Hulu` label.

* **Trending All:** Hidden.
* **Trending Netflix:** Hidden.
* **Trending Hulu:** Visible.
* **Recently Added / Action / Sci-Fi / Romance:** Visible (thanks to the `Network_Hulu` collection label).
* *The Magic Trick:* Inside the "Action" collection, it dynamically hides your local movies and the Netflix movies, only displaying Hulu action movies like *Prey*.

---

**This gives you complete granular control over your real household users, while automating the perfect "App Illusion" for the streaming profiles. Would you like me to show you how to set up the webhooks so Kometa automatically updates these smart collections whenever your pipeline adds new media?**