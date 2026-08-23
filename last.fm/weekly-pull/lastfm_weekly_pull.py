#!/usr/bin/env python3
"""
Pull Last.fm weekly artist chart data for a user across their full
scrobbling history, using the periods returned by user.getWeeklyChartList.

Usage:
    export LASTFM_API_KEY=your_key_here
    python3 lastfm_weekly_pull.py --user USERNAME --output weekly_top_artists.csv
    python3 lastfm_weekly_pull.py --user USERNAME --output weekly_top_artists.ndjson --top-n 10

Resume an interrupted run (skips weeks already in the output file):
    python3 lastfm_weekly_pull.py --user USERNAME --output weekly_top_artists.csv --resume

Requires: requests  (pip install requests)

Get an API key at: https://www.last.fm/api/account/create
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

API_BASE = "https://ws.audioscrobbler.com/2.0/"


def api_call(params, api_key, max_retries=5):
    """
    Call the Last.fm API with basic retry/backoff on rate limiting or transient errors. This is a serial pull and can be 
    speeded up using asyncio or multiprocessing if desired, but the Last.fm API is rate-limited to 5 requests per second per IP, so
    be careful not to exceed that.
    """
    params = dict(params)
    params["api_key"] = api_key
    params["format"] = "json"

    for attempt in range(1, max_retries + 1):
        resp = requests.get(API_BASE, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if "error" in data:
                # error code 29 = rate limit exceeded
                if data.get("error") == 29 and attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Last.fm API error {data.get('error')}: {data.get('message')}")
            return data
        if resp.status_code == 429 and attempt < max_retries:
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
    raise RuntimeError("Exceeded max retries calling Last.fm API")


def get_weekly_chart_list(user, api_key):
    data = api_call({"method": "user.getweeklychartlist", "user": user}, api_key)
    return data["weeklychartlist"]["chart"]


def get_weekly_artist_chart(user, from_ts, to_ts, api_key):
    data = api_call(
        {"method": "user.getweeklyartistchart", "user": user, "from": from_ts, "to": to_ts},
        api_key,
    )
    artists = data.get("weeklyartistchart", {}).get("artist", [])
    if isinstance(artists, dict):  # last.fm collapses a single-item list to a dict
        artists = [artists]
    return artists


def fmt_date(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def load_done_weeks(path):
    """
    Read an existing output file so a resumed run skips weeks already fetched.
    """
    done = set()
    if not os.path.exists(path):
        return done
    if path.endswith(".csv"):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(row["from_ts"])
    elif path.endswith((".ndjson", ".jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    done.add(str(json.loads(line)["from_ts"]))
    return done


def main():
    parser = argparse.ArgumentParser(description="Pull Last.fm weekly artist charts for a user")
    parser.add_argument("--user", required=True, help="Last.fm username")
    parser.add_argument("--output", default="weekly_top_artists.csv", help="Output file (.csv or .ndjson)")
    parser.add_argument("--top-n", type=int, default=10, help="How many top artists to keep per week")
    parser.add_argument("--delay", type=float, default=0.25, help="Seconds to sleep between API calls")
    parser.add_argument("--resume", action="store_true", help="Skip weeks already present in --output")
    args = parser.parse_args()

    api_key = os.environ.get("LASTFM_API_KEY")
    if not api_key:
        sys.exit("Set LASTFM_API_KEY environment variable first.")

    print(f"Fetching week list for {args.user} ...")
    weeks = get_weekly_chart_list(args.user, api_key)
    print(f"{len(weeks)} weeks found.")

    done = load_done_weeks(args.output) if args.resume else set()
    if done:
        print(f"Resuming: {len(done)} weeks already fetched, skipping those.")

    is_ndjson = args.output.endswith((".ndjson", ".jsonl"))
    append_mode = args.resume and os.path.exists(args.output)
    mode = "a" if append_mode else "w"

    csv_file = csv_writer = ndjson_file = None
    if is_ndjson:
        ndjson_file = open(args.output, mode, encoding="utf-8")
    else:
        csv_file = open(args.output, mode, newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        if not append_mode:
            csv_writer.writerow(
                ["week_start", "week_end", "from_ts", "to_ts", "rank", "artist", "mbid", "playcount"]
            )

    try:
        for i, week in enumerate(weeks, 1):
            from_ts, to_ts = week["from"], week["to"]
            if from_ts in done:
                continue

            week_start, week_end = fmt_date(from_ts), fmt_date(to_ts)
            print(f"[{i}/{len(weeks)}] {week_start} -> {week_end}", end=" ")

            try:
                artists = get_weekly_artist_chart(args.user, from_ts, to_ts, api_key)
            except RuntimeError as e:
                print(f"ERROR: {e}")
                continue

            top = artists[: args.top_n]
            print(f"({len(artists)} artists this week, top: {top[0]['name'] if top else 'none'})")

            if not top:
                # No scrobbles that week — still record it so gaps show up in analysis
                row = {"week_start": week_start, "week_end": week_end, "from_ts": from_ts,
                       "to_ts": to_ts, "rank": None, "artist": None, "mbid": None, "playcount": 0}
                if is_ndjson:
                    ndjson_file.write(json.dumps(row) + "\n")
                else:
                    csv_writer.writerow([week_start, week_end, from_ts, to_ts, "", "", "", 0])

            for artist in top:
                record = {
                    "week_start": week_start,
                    "week_end": week_end,
                    "from_ts": from_ts,
                    "to_ts": to_ts,
                    "rank": artist.get("@attr", {}).get("rank"),
                    "artist": artist.get("name"),
                    "mbid": artist.get("mbid") or None,
                    "playcount": int(artist.get("playcount", 0)),
                }
                if is_ndjson:
                    ndjson_file.write(json.dumps(record) + "\n")
                else:
                    csv_writer.writerow([record["week_start"], record["week_end"], record["from_ts"],
                                          record["to_ts"], record["rank"], record["artist"],
                                          record["mbid"], record["playcount"]])

            (ndjson_file or csv_file).flush()
            time.sleep(args.delay)
    finally:
        if csv_file:
            csv_file.close()
        if ndjson_file:
            ndjson_file.close()

    print(f"Done. Written to {args.output}")


if __name__ == "__main__":
    main()
