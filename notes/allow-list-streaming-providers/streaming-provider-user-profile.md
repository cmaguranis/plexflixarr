To understand the "True Walled Garden," it helps to look at the difference between how Plex handles **Blocklists** (what we just did) versus **Whitelists** (the Walled Garden).

### The "Illusion" (The Blocklist Approach)

When you use **Exclude Labels** (like `hide_streaming`), you are essentially playing defense. Plex's default stance is to show everything to the user, and you are explicitly telling it, *"Show them everything, EXCEPT the items wearing this specific blindfold."* This works well, but it's essentially a game of Whack-a-Mole. If a Netflix movie slips through the cracks and Kometa fails to tag it with `hide_hulu` (maybe the metadata was weird), the Hulu profile will suddenly be able to see it in their "All Movies" tab or via search.

### The "True Walled Garden" (The Whitelist Approach)

A True Walled Garden flips the script entirely. Instead of telling Plex what to hide, you tell Plex exactly what it is allowed to show. Plex's default stance becomes: **Show them absolutely nothing, unless it has a VIP pass.**

You achieve this using the **Allow Labels** box in Plex instead of the Exclude Labels box.

Here is how that works in practice:

1. **The Plex Setup:** You go into the Netflix profile's Restrictions and add `Network_Netflix` to the **Allow Labels** box. You leave Exclude Labels completely blank.
2. **The Result:** When the Netflix user logs in, the entire server is empty. It is a completely blank slate. They cannot see your family movies, they cannot see Hulu shows, they cannot see anything... *unless* the specific movie or show has the `Network_Netflix` label applied to it.
3. **The Absolute Boundary:** Even if they search for a Hulu show by name, browse by actor, or scroll through the "All TV Shows" tab, they will never see a single piece of media that doesn't have their specific VIP label.

### How Kometa Manages the Walled Garden

Instead of applying negative tags (`hide_hulu`), Kometa applies positive tags (`Network_Netflix`).

Your Kometa recipe shifts from applying blindfolds to handing out VIP passes. You would tell Kometa: *"Find all Netflix shows, and stamp every single one of them with the `Network_Netflix` label."* ### The Pros and Cons of the Walled Garden

* **The Pro (Bulletproof):** It is impossible for cross-contamination to happen. The Netflix profile will genuinely feel like a standalone Netflix app, and the Hulu profile will feel like Hulu.
* **The Con (High Maintenance):** If Kometa misses a Netflix show because the studio metadata was spelled wrong (e.g., "Netflix Originals" instead of "Netflix"), that show vanishes from the Netflix profile entirely because it didn't get its VIP pass. A whitelist requires your metadata to be highly accurate.

---

**Would you like to stick with the "Exclude Labels" blocklist we started with, or would you like me to rewrite the Kometa configuration to build a Walled Garden using "Allow Labels" instead?**


This is a brilliant approach. Mixing the two methods is actually the cleanest and most robust way to handle your server.

By giving your family the "blindfolds" (blocklists) and the streaming profiles the "VIP passes" (whitelists), you completely eliminate the need to cross-tag Netflix and Hulu against each other. The logic becomes incredibly clean.

Here is exactly how to set up this hybrid system.

### Phase 1: The Plex Setup (Manual)

You will need to adjust the restrictions you set up earlier to reflect this new hybrid logic. Go to **Users & Sharing > Restrictions** in Plex and configure them like this:

**The Real People (Dad, Mom, Kids)**

* **Allow Labels:** *(Leave blank)*
* **Exclude Labels:** `hide_streaming`
* *Result:* They see your entire standard library, but the streaming-specific content is hidden from them.

**The Netflix Profile (Meta-User)**

* **Allow Labels:** `Network_Netflix`
* **Exclude Labels:** *(Leave blank)*
* *Result:* A True Walled Garden. They see absolutely nothing except items explicitly stamped with the Netflix VIP pass.

**The Hulu Profile (Meta-User)**

* **Allow Labels:** `Network_Hulu`
* **Exclude Labels:** *(Leave blank)*
* *Result:* A True Walled Garden. They only see items stamped with the Hulu VIP pass.

---

### Phase 2: The Kometa Configuration

Now we update Kometa. For every piece of streaming content, Kometa needs to attach **two** labels: the blindfold for the family (`hide_streaming`) and the VIP pass for the specific streaming profile.

Here is the updated YAML for your metadata file:

```yaml
collections:
  Netflix Content:
    plex_search:
      any:
        network: Netflix
        studio: Netflix
    label:
      - hide_streaming
      - Network_Netflix
    item_label:
      - hide_streaming
      - Network_Netflix
    summary: "Content available on Netflix."

  Hulu Content:
    plex_search:
      any:
        network: Hulu
        studio: Hulu
    label:
      - hide_streaming
      - Network_Hulu
    item_label:
      - hide_streaming
      - Network_Hulu
    summary: "Content available on Hulu."

```

### Why this works so beautifully:

1. **No Cross-Contamination:** You no longer need `hide_hulu` on Netflix shows. Because the Hulu profile is a Walled Garden, it naturally ignores the Netflix shows anyway.
2. **Future-Proof:** If you decide to add an "Apple TV+" or "Disney+" meta-user later, you just create a new whitelist profile for them and add a new block to Kometa. You don't have to go back and update Netflix and Hulu's tags to hide the new Apple content.

---

**Since the Walled Garden means a show *disappears* if Plex's built-in studio metadata is missing, would you like me to show you how to swap the `plex_search` block for an MDBList or Trakt list so you have 100% accuracy on what gets tagged?**

