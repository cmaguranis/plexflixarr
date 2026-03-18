Here is the complete implementation and configuration plan using the **"Hide From" (Blocklist)** strategy.

This approach ensures your main library remains fully intact for everyone, while giving you exact, stackable control over which collections appear on which user's Home Screen.

---

### Phase 1: Plex Profile Setup (One-Time "Blindfold" Configuration)

First, we need to configure each user profile in Plex to reject a specific label. You only have to do this once.

1. Open **Plex Web** (app.plex.tv) and go to **Settings (Wrench Icon)**.
2. Navigate to **Users & Sharing** on the left sidebar.
3. **For the Dad Profile:**
* Click Edit (Pencil Icon) > **Restrictions**.
* Scroll down to the specific library (e.g., Movies).
* In the **Exclude Labels** box, type `hide_dad` and hit Enter. Save.


4. **For the Mom Profile:**
* Repeat the process, but in the **Exclude Labels** box, type `hide_mom`. Save.


5. **For the Kids Profile:**
* Repeat the process, but in the **Exclude Labels** box, type `hide_kids`. Save.



*Note: The Admin profile (You) cannot have Restrictions applied. You see everything by default unless you toggle it off using Kometa's `visible_home` setting.*

---

### Phase 2: Kometa Configuration (The YAML)

Now, Plex is programmed so that everyone sees everything in the "Shared Users" pool *unless* a collection possesses their specific "hide" label.

Here is how you write your Kometa YAML to control visibility using this logic.

**Example 1: Visible to Mom and Kids (Hidden from Dad)**

```yaml
collections:
  Family Movie Night:
    smart_filter:
      all:
        genre: Family
    # Dad is blindfolded; Mom and Kids see it normally
    label: hide_dad
    visible_home: true       # Shows on Admin Home Screen
    visible_shared: true     # Pushes to Shared Users (Mom & Kids)

```

**Example 2: Visible to Mom Only (Hidden from Dad and Kids)**

```yaml
collections:
  Mom's Rom-Coms:
    smart_filter:
      all:
        genre: Romance
    # Stack the labels to blindfold both Dad and Kids
    label: 
      - hide_dad
      - hide_kids
    visible_home: true       
    visible_shared: true     

```

**Example 3: Visible to Kids Only (Hidden from Admin, Dad, and Mom)**

```yaml
collections:
  Weekend Cartoons:
    smart_filter:
      all:
        genre: Animation
        content_rating: G, PG
    # Blindfold Dad and Mom
    label:
      - hide_dad
      - hide_mom
    visible_home: false      # Admin toggle: Hides from Admin Home Screen
    visible_shared: true     # Pushes to Shared Users (Kids only, due to labels)

```

---

### Phase 3: Execution and Verification

1. **Run Kometa:** Execute your script so it creates these collections and applies the labels to the collection metadata.
2. **Verify the Labels in Plex:** * As Admin, go to your Movies library and click the **Collections** tab.
* Edit "Mom's Rom-Coms" and check the **Sharing** tab. You should see both `hide_dad` and `hide_kids` populated in the Labels box.


3. **Test the Home Screens:**
* Switch to the **Kids** profile. They should see "Family Movie Night" and "Weekend Cartoons", but not "Mom's Rom-Coms".
* Switch to the **Dad** profile. He should not see "Family Movie Night", "Mom's Rom-Coms", or "Weekend Cartoons".



**Would you like to review how to apply this exact same logic to dynamically built "Top 10" or "Trending" lists using Trakt or IMDb integrations in Kometa?**

## Managing the custom created collections (Kdrama, KTV, reality tv)

If you want to keep all your home screen logic in your Kometa YAML so it acts as a "backup" for your server's configuration, you can tell Kometa to manage the collection's visibility without touching the items inside it.

The trick is to leave out the builder (no smart_filter, no trakt_list, etc.). If you just define the collection name and the settings, Kometa will look for the existing collection in Plex, apply the labels and visibility toggles, and leave your custom-ordered movies completely alone.

Here is what you add to your Kometa YAML:

```yaml
collections:
  "Name of Your Custom Collection":
    # Notice there are no builders/filters defined here! 
    # This tells Kometa to act strictly as a metadata manager for this collection.
    
    label: hide_dad          # Blindfolds Dad
    visible_home: true       # Pins to your Admin Home Screen
    visible_shared: true     # Pushes to Shared Users Home Screen
```

**A quick word of caution if you use Method 2:**
Never add a builder (like plex_search or smart_filter) to this specific collection in your YAML in the future. If you do, Kometa will overwrite your manual drag-and-drop ordering with whatever sorting logic the builder uses.