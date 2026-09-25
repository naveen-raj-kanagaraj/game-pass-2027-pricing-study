"""
Xbox Game Pass pricing study - YouTube comment collection.

Collects comments on videos covering two events:
  E1  2025-10-01  Game Pass Ultimate $19.99 -> $29.99  (+50%)
  E2  2026-04-21  Game Pass Ultimate $29.99 -> $22.99  (-23%)

Two modes:
  python src/collect_youtube.py --from-ids   re-fetch the exact 7,978 comments used in the study
                                             from data/comments/comment_ids.csv (recommended)
  python src/collect_youtube.py --search     run the original search (results drift over time)

Output: data/comments/comments.csv
Set your key first:  export YOUTUBE_API_KEY=...   (never commit it)
Quota use: under 1,000 of 10,000 daily units.
"""

import csv, os, sys, time, requests

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
OUT = "data/comments/comments.csv"

MAX_VIDEOS_PER_QUERY   = 8
MAX_COMMENTS_PER_VIDEO = 400

BASE = "https://www.googleapis.com/youtube/v3"

EVENTS = {
    "E1_increase": {
        "after": "2025-09-25T00:00:00Z",
        "before": "2025-11-15T00:00:00Z",
        "queries": [
            "xbox game pass price increase",
            "game pass ultimate price hike",
            "xbox game pass 29.99",
        ],
    },
    "E2_cut": {
        "after": "2026-04-15T00:00:00Z",
        "before": "2026-06-01T00:00:00Z",
        "queries": [
            "xbox game pass price cut",
            "game pass price drop",
            "xbox game pass 22.99",
        ],
    },
}


def api_get(endpoint, params):
    """One API call with basic error surfacing."""
    params["key"] = API_KEY
    r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"{endpoint} HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def find_videos(query, after, before, limit):
    """Search videos in a date window. Costs 100 quota units per call."""
    data = api_get("search", {
        "part": "snippet", "q": query, "type": "video",
        "order": "relevance", "maxResults": min(limit, 50),
        "publishedAfter": after, "publishedBefore": before,
        "relevanceLanguage": "en", "regionCode": "US",
    })
    out = []
    for item in data.get("items", []):
        out.append({
            "video_id":     item["id"]["videoId"],
            "title":        item["snippet"]["title"],
            "channel":      item["snippet"]["channelTitle"],
            "published_at": item["snippet"]["publishedAt"],
        })
    return out


def fetch_comments(video_id, cap):
    """Page through top-level comments. Costs 1 unit per 100 comments."""
    rows, token = [], None
    while len(rows) < cap:
        params = {
            "part": "snippet", "videoId": video_id,
            "maxResults": 100, "order": "relevance", "textFormat": "plainText",
        }
        if token:
            params["pageToken"] = token
        try:
            data = api_get("commentThreads", params)
        except RuntimeError as e:
            # comments disabled / video private -> skip quietly
            print(f"      skipped ({str(e)[:60]})")
            break
        for item in data.get("items", []):
            s = item["snippet"]["topLevelComment"]["snippet"]
            rows.append({
                "video_id":   video_id,
                "comment_id": item["id"],
                "published_at": s["publishedAt"],
                "likes":      s.get("likeCount", 0),
                "text":       s.get("textDisplay", "").replace("\n", " ").strip(),
            })
        token = data.get("nextPageToken")
        if not token:
            break
        time.sleep(0.2)
    return rows[:cap]


def from_ids():
    ids = list(csv.DictReader(open("data/comments/comment_ids.csv", encoding="utf-8")))
    meta = {r["comment_id"]: r for r in ids}
    rows, keys = [], list(meta)
    for i in range(0, len(keys), 50):
        batch = keys[i:i + 50]
        r = requests.get(f"{BASE}/comments", params={"part": "snippet", "id": ",".join(batch),
                         "textFormat": "plainText", "maxResults": 50, "key": API_KEY}, timeout=30)
        r.raise_for_status()
        for it in r.json().get("items", []):
            m = meta[it["id"]]
            rows.append({"video_id": m["video_id"], "comment_id": it["id"], "published_at": m["published_at"],
                         "likes": m["likes"], "text": it["snippet"].get("textDisplay", ""), "event": m["event"]})
        time.sleep(0.1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["video_id", "comment_id", "published_at", "likes", "text", "event"])
        w.writeheader(); w.writerows(rows)
    print(f"Re-fetched {len(rows)} of {len(keys)} comments (deleted comments cannot be recovered). Wrote {OUT}")


def main():
    if not API_KEY:
        raise SystemExit("Set YOUTUBE_API_KEY first, e.g. export YOUTUBE_API_KEY=your_key")
    if "--from-ids" in sys.argv:
        return from_ids()

    videos, comments, seen = [], [], set()

    for event, cfg in EVENTS.items():
        print(f"\n=== {event} ===")
        for q in cfg["queries"]:
            print(f"  searching: {q}")
            try:
                found = find_videos(q, cfg["after"], cfg["before"], MAX_VIDEOS_PER_QUERY)
            except RuntimeError as e:
                print(f"    SEARCH FAILED: {e}")
                continue
            for v in found:
                if v["video_id"] in seen:
                    continue
                seen.add(v["video_id"])
                v["event"] = event
                v["search_query"] = q
                print(f"    {v['channel'][:28]:30} {v['title'][:52]}")
                got = fetch_comments(v["video_id"], MAX_COMMENTS_PER_VIDEO)
                v["n_comments"] = len(got)
                for c in got:
                    c["event"] = event
                comments.extend(got)
                videos.append(v)
                print(f"      -> {len(got)} comments")

    if not videos:
        raise SystemExit("No videos found. Check the API key is valid and the API is enabled.")

    os.makedirs("data/comments", exist_ok=True)
    with open("data/comments/videos_search_run.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(videos[0].keys()))
        w.writeheader(); w.writerows(videos)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(comments[0].keys()))
        w.writeheader(); w.writerows(comments)

    print(f"\nDONE  videos={len(videos)}  comments={len(comments)}")
    for e in EVENTS:
        nv = sum(1 for v in videos if v["event"] == e)
        nc = sum(1 for c in comments if c["event"] == e)
        print(f"   {e}: {nv} videos, {nc} comments")
    print(f"\nWrote {OUT}. Note: search results drift; use --from-ids to reproduce the study exactly.")


if __name__ == "__main__":
    main()
