# 📄 Daily Last.fm Scrobble Snapshot Script  
*A structured overview of the design, decisions, and challenges behind the daily scrobble‑snapshot pipeline.*

## 1. Purpose  
This script retrieves **all scrobbles from “yesterday”** for the specified Last.fm user, filters out invalid entries, and stores the results in a **CSV snapshot**. Each run produces a clean, analysis‑ready dataset that can be used for:

- Time‑series analysis  
- Daily deltas  
- Listening‑pattern visualisation  
- MusicBrainz enrichment  
- Aggregated charts  

The script is intentionally simple, stable, and predictable, designed for long‑term use and can be refactored to suit different APIs or a Cloud Run function.

---

## 2. Key Features
- **UTC‑based time‑range filtering** using UNIX timestamps  
- **Automatic exclusion** of Last.fm’s “now playing” track  
- **Filtering out scrobbles outside the desired window**  
- **Clean CSV output** with stable schema  
- **Snapshot timestamp** for later delta analysis  
- **Environment‑based configuration** via `.env`  

---

## 3. Why UNIX timestamps and UTC?  
Last.fm’s API requires `from` and `to` parameters in **UNIX timestamp format**, and explicitly states:

> “This must be in the UTC time zone.”

To ensure correctness, the script computes:

- `y_start` → yesterday at **00:00:00 UTC**  
- `y_end` → yesterday at **23:59:59 UTC**

This guarantees that the API returns only scrobbles from the intended day, regardless of the user’s local timezone.

---

## 4. The “Now Playing” Bug  
One of the biggest challenges was discovering that Last.fm **always returns the most recent track**, even if it falls *outside* the requested time range. This track may include:

- `@attr: { nowplaying: "true" }`  
- No `date` field  
- A timestamp greater than `y_end`  

What I discovered was that if you are scrobbling music at the time the script is running then it will pick up this data artefact. It's not documented.

This caused the script to incorrectly include a track from *today* alongside yesterday’s scrobbles, and consequently I went around in circles trying to figure it out.

### ✔️ Solution  
I added explicit filtering:

- Skip entries with `nowplaying="true"`  
- Skip entries missing a `date`  
- Skip entries whose `uts` timestamp is outside `[y_start, y_end]`

This ensures the dataset contains **only** valid scrobbles from yesterday.

---

## 5. CSV Schema Decisions  
The CSV schema is intentionally simple but structured enough for future analysis:

| Column | Description |
|--------|-------------|
| `timestamp` | When the snapshot was taken |
| `rank` | Position within the filtered list |
| `name` | Track name |
| `url` | Track URL |

This meets the immediate requirement: **store yesterday’s scrobbles cleanly**.

Later, you can expand the schema using CSV schema improvements if you want:

- MBIDs  
- Artist/album fields  
- Scrobble timestamps  
- Human‑readable datetime  
- Enrichment metadata  

But for now, the minimal schema keeps the file lightweight and easy to parse.

---

## 6. Script Flow  
1. Load environment variables  
2. Compute yesterday’s UTC time range  
3. Call `user.getRecentTracks` with `from` and `to`  
4. Filter out invalid entries  
5. Build structured rows  
6. Append to CSV (create if missing)  
7. Print confirmation  

This flow is stable and predictable, which is ideal for daily automation.

---

## 7. Challenges Solved  
### **1. Incorrect time filtering**  
The API returned extra tracks because Last.fm ignores `from`/`to` for the most recent scrobble.  
**Fixed via manual filtering.**

### **2. Misleading variable naming**  
The API returns tracks, but the script originally used `artists` as the variable name.  
**Renamed to avoid confusion.**

### **3. Missing timestamps**  
Some scrobbles lack a `date` field.  
**Filtered out to avoid crashes.**

### **4. CSV schema limitations**  
The original schema was too minimal for future analysis.  
**Improved schema documented for future expansion.**

---

## 8. Future Extensions  
If you want to expand this pipeline later, here are natural next steps:

- Add MBIDs  
- Daily delta analysis  
- MusicBrainz enrichment  
- Daily chart generation  
- Unified artist/track analytics

Each of these builds on the clean foundation already established here. I created this as an exercise with a view to automating data collection as part of a data ingest pipeline.

---

## 9. Summary  
This script provides a reliable, timestamp‑accurate snapshot of yesterday’s scrobbles. The main challenges, Last.fm’s “now playing” quirk, timestamp filtering, and CSV schema design, have been solved in a way that keeps the pipeline simple while leaving room for future projects.

It's a great way to experiment further with other endpoints and aggregating data, linking it via the MBIDs to MusicBrainz and building something interesting.


---

## 10. Installing and Running the Script
There is a requirements.txt file so you will need to create a venv and install the packages.

Add your Last.fm API key to an external .env file. Feel free to move all the variables to this external file. I hardcoded the above to keep things simple for this repo.

It works for the intended purpose so read through it before running!

You're free to use this script anyway you want. It's provided as is, with no warranties or support! I'm not liable for any loss blah blah blah. 

