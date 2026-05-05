# Demo 1 — Ambient Sense

**Prompt:** `nimbus ask "Describe what's around me right now."`

<!-- TODO: replace with a real terminal transcript captured via `nimbus ask` -->

**Expected agent behavior:**
1. Calls `stats()` to verify the collector is running
2. Calls `who_is_here(since="5m", min_observations=3)`
3. Summarizes the result in natural language

**Example output:**
```
Three phones (two Apple, one Samsung), one Sonos speaker, your laptop,
seven neighbor Wi-Fi networks, and two AirTags — one of which has been
here for nine hours.
```
