import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import csv
import time

# Load .env file
load_dotenv() 

# secrets/tokens/keys defined in external .env file.
API_KEY = os.getenv("API_KEY")
BASE_URL = "https://ws.audioscrobbler.com/2.0"
LAST_FM_USER = "YOUR_USERNAME" 

# timestamp = datetime.now(timezone.utc)
timestamp = datetime.now().isoformat()

def api_call(method, limit):
    params = {
        "method": method,
        "api_key": API_KEY,
        "format": "json",
        "user": LAST_FM_USER,
        "from": y_start,
        "to": y_end,
        "limit": limit
    }

    r = requests.get(BASE_URL, params=params)

    # If HTTP error (403, 404, 500, etc.)
    try:
        r.raise_for_status()
    except Exception as e:
        print("HTTP error:", e)
        print("Raw response:", r.text[:500])
        raise

    # Try JSON decode
    try:
        data = r.json()
    except ValueError:
        print("Failed to decode JSON.")
        print("Raw response:", r.text[:500])
        raise

    # Last.fm sometimes returns error objects inside JSON
    if "error" in data:
        raise Exception(f"Last.fm API error {data['error']}: {data.get('message')}")

    return data

def yesterday_range_utc():
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    start = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0, tzinfo=timezone.utc)
    end   = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59, tzinfo=timezone.utc)

    return int(start.timestamp()), int(end.timestamp())

y_start, y_end = yesterday_range_utc()

# Print converted start and end times to validate it's working as intended
# print("Yesterday start:", y_start)
# print("Yesterday end:", y_end)

# Convert start date to something human readable and print to validate, uncomment both lines to check date
# formatted_time = time.strftime('%Y-%m-%d', time.gmtime(y_start))
# print("date:", formatted_time)

def fetch_user_recent_tracks(limit=750):
    '''
    Call the api method and fetch the last x amount of tracks from yesterday, time uses epoch, converted to UTC, should be 00:00:00 to 23:59:59.
    Note the cleaning loop. There's a quirk in the API that returns the latest playing track if one is playing when the script runs. This means
    that you'll get an addtional track added to the list of tracks played even if it is outside your from/to time range.
    
    The first element of artists is often {"@attr": {"nowplaying": "true"}, ...}, or simply a track with a timestamp greater than your y_end.
    This track is not part of yesterday, it’s just the most recent scrobble.

    I've include a cleaning loop inside the function, this removes:
    * The “now playing” track
    * Any track outside your from/to range
    * Any malformed track without a timestamp
    '''

    data = api_call("user.getRecentTracks", limit)
    tracks = data["recenttracks"]["track"]
    timestamp = datetime.now(timezone.utc)

    cleaned = []

    for t in tracks:
        # Skip "now playing" entries
        if "@attr" in t and t["@attr"].get("nowplaying") == "true":
            continue

        # Skip tracks without a date (rare but happens)
        if "date" not in t:
            continue

        uts = int(t["date"]["uts"])

        # Keep only tracks inside yesterday's range
        if uts < y_start or uts > y_end:
            continue

        cleaned.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scrobble_uts": uts,
            "scrobble_datetime": datetime.fromtimestamp(uts, tz=timezone.utc).isoformat(),
            "rank": len(cleaned) + 1,
            "artist_name": t["artist"]["#text"],
            "track_name": t["name"],
            "album_name": t.get("album", {}).get("#text", ""),
            "artist_mbid": t["artist"].get("mbid", ""),
            "track_mbid": t.get("mbid", ""),
            "album_mbid": t.get("album", {}).get("mbid", ""),
            "url": t["url"],
        })

    return cleaned

def append_csv(filename, rows, fieldnames):
    '''
    Send output to existing file if it exists, if not create it, otherwise amend to it.
    '''
    file_exists = os.path.isfile(filename)

    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        for row in rows:
            writer.writerow(row)

if __name__ == "__main__":
    artists = fetch_user_recent_tracks()
    

    append_csv(
        "user_get_recent_tracks.csv",
        artists,
        [
            "timestamp",
            "scrobble_uts",
            "scrobble_datetime",
            "rank",
            "artist_name",
            "track_name",
            "album_name",
            "artist_mbid",
            "track_mbid",
            "album_mbid",
            "url",
        ]
    )

    print("Snapshot saved.")
