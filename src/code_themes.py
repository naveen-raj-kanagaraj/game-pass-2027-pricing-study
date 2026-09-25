"""
Code 7,978 YouTube comments into themes and segments with transparent keyword rules.

Input : data/comments/comments.csv  (columns: video_id, comment_id, published_at, likes, text, event)
        Re-create it with src/collect_youtube.py; comment text is not redistributed (YouTube API terms).
Output: outputs/theme_shares.csv, outputs/segment_counts.csv, printed summary.

Rules are case-insensitive regular expressions. A comment can match several themes.
Sentiment: VADER compound score; net sentiment = share positive (>0) minus share negative (<0).
Theme counts are the robust measure; VADER misreads sarcasm.
"""
import sys, os, warnings
warnings.filterwarnings("ignore")
import pandas as pd

THEMES = {
    "price_or_value":        r"\bpric|\bcost|expensive|cheap|afford|\bvalue\b|worth\b|\$\d",
    "call_of_duty":          r"call of duty|\bcod\b|black ops|warzone",
    "playstation":           r"playstation|\bps ?[45]\b|\bps ?plus\b|\bsony\b",
    "steam":                 r"\bsteam\b",
    "own_or_buy_instead":    r"backlog|buy (?:the |my |a )?games?|just buy|own my games|buying games|physical",
    "day_one_releases":      r"day one|day-one|day 1\b|launch day",
    "cloud_gaming":          r"\bcloud\b|xcloud",
    "backward_compatibility":r"backward|backwards compat|back compat",
    "cancellation":          r"cancel",
    "rival_any":             r"playstation|\bps ?[45]\b|\bsony\b|\bsteam\b|nintendo|\bswitch\b",
    "switching_explicit":    r"switch(?:ing|ed)? to (?:playstation|ps|sony|steam|pc|nintendo)|going (?:back )?to (?:playstation|ps|pc|steam)|moving to (?:playstation|ps|pc|steam)",
    "trust":                 r"\btrust|greed|scam|lied|\bshady\b|disrespect",
    "too_late":              r"too late",
    "downgrade":             r"downgrad",
}
SEGMENTS = {
    "new_release_player": THEMES["call_of_duty"] + r"|" + THEMES["day_one_releases"] + r"|new releases?|new games",
    "backlog_player":     THEMES["own_or_buy_instead"],
    "loyalist_who_left":  r"\b(?:1\d|20)\+? ?(?:years|yrs)\b|since (?:19|20)\d\d|since the (?:original|og|360)|\bloyal",
}

def code(df):
    t = df["text"].fillna("").str.lower()
    for k, p in {**THEMES, **{"seg_" + k: v for k, v in SEGMENTS.items()}}.items():
        df[k] = t.str.contains(p, regex=True)
    return df

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "data/comments/comments.csv"
    df = pd.read_csv(src)
    if "sent" not in df:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        sia = SentimentIntensityAnalyzer()
        df["sent"] = df["text"].fillna("").map(lambda t: sia.polarity_scores(t)["compound"])
    df = code(df)
    shares = (df.groupby("event")[list(THEMES)].mean() * 100).round(1).T
    shares.columns = ["at_increase_pct", "at_cut_pct"]
    seg = df[["seg_" + k for k in SEGMENTS]].sum().rename("comments")
    net = df.groupby("event")["sent"].apply(lambda s: round(((s > 0).mean() - (s < 0).mean()) * 100, 1))
    os.makedirs("outputs", exist_ok=True)
    shares.to_csv("outputs/theme_shares.csv"); seg.to_csv("outputs/segment_counts.csv")
    print(df.groupby("event").size().to_string(), "\n")
    print(shares.to_string(), "\n")
    print(seg.to_string(), "\n  segments cover", int(df[["seg_" + k for k in SEGMENTS]].any(axis=1).sum()), "comments")
    print("\nnet sentiment %:", net.to_dict())
    net.rename("net_sentiment_pct").to_csv("outputs/net_sentiment.csv")
