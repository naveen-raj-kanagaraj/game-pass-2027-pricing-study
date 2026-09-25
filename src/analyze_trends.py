"""
Reproduce every search-data figure in the decks from the raw Google Trends exports.

Figures:
  29.3x / 2.9x  peak daily "cancel game pass" searches, each event against its own baseline
                (baseline = mean of days -45 to -3 before the announcement)
  10 days       the increase: daily searches back under 4x baseline for good (within 30 days)
  202 days      1 Oct 2025 (increase) to 21 Apr 2026 (cut)
  2.7x          Godot search interest, Sep 2025 against the year before Unity's fee (12 Sep 2023)
  1.97 -> 5.81  Godot-to-Unity interest ratio, same windows
  3 wks         weeks until Unity's own interest fell back to its 26-week pre-fee average
  robustness    weekly cancel searches divided by general "xbox game pass" interest

Usage: python src/analyze_trends.py        (writes outputs/trend_metrics.json)
"""
import json, os
import pandas as pd

D = "data"
def read(path):
    df = pd.read_csv(path, skiprows=2)
    df.columns = ["t", "v"]
    df["v"] = pd.to_numeric(df["v"].astype(str).str.replace("<1", "0.5"), errors="coerce")
    df["t"] = pd.to_datetime(df["t"])
    return df.set_index("t")["v"]

def event(series, day0):
    d0 = pd.Timestamp(day0)
    base = series[d0 - pd.Timedelta(days=45): d0 - pd.Timedelta(days=3)].mean()
    mult = series / base
    window = mult[d0 - pd.Timedelta(days=3): d0 + pd.Timedelta(days=3)]
    after = mult[d0: d0 + pd.Timedelta(days=30)]
    over4 = after[after >= 4]
    faded = (over4.index.max() - d0).days + 1 if len(over4) else 0
    return {"baseline_index": round(base, 2), "peak_multiple": round(window.max(), 1),
            "peak_day": (window.idxmax() - d0).days, "days_until_under_4x": faded}

m = {}
m["increase_2025_10_01"] = event(read(f"{D}/google_trends/trends_daily_event1.csv"), "2025-10-01")
m["cut_2026_04_21"]      = event(read(f"{D}/google_trends/trends_daily_event2.csv"), "2026-04-21")
m["days_increase_to_cut"] = (pd.Timestamp("2026-04-21") - pd.Timestamp("2025-10-01")).days

cancel = read(f"{D}/google_trends/trends_cancel_gamepass.csv")
general = read(f"{D}/google_trends/trends_gamepass_general.csv")
ratio = (cancel / general.replace(0, pd.NA)).dropna()
pre = ratio["2025-08-01":"2025-09-27"].mean()
m["robustness_weekly_ratio"] = {
    "pre_increase_mean": round(pre, 3),
    "week_of_increase_multiple": round(ratio["2025-09-28":"2025-10-04"].max() / pre, 1),
    "week_of_cut_multiple": round(ratio["2026-04-19":"2026-04-25"].max() / pre, 1),
}

# Notice precedent: weekly cancel searches in the announcement week, against the eight weeks before.
# Jul 2024: Ultimate +18%, existing members paid more from 12 Sep 2024 (two months' notice).
# Oct 2025: Ultimate +50%, in effect for new members the same day.
def week_jump(day):
    d = pd.Timestamp(day)
    base = cancel[d - pd.Timedelta(days=62): d - pd.Timedelta(days=7)].mean()
    return round(cancel[d - pd.Timedelta(days=6): d + pd.Timedelta(days=6)].max() / base, 1)
m["notice_precedent_weekly"] = {"jul_2024_with_notice": week_jump("2024-07-10"),
                                "oct_2025_increase": week_jump("2025-10-01")}

g = read(f"{D}/unity_godot/godot.csv"); u = read(f"{D}/unity_godot/unity.csv")
fee = pd.Timestamp("2023-09-12")
pre_g = g[fee - pd.Timedelta(weeks=52): fee - pd.Timedelta(days=1)]
post_g = g["2025-09-01":"2025-09-30"]
r = g / u
u_base = u[fee - pd.Timedelta(weeks=26): fee - pd.Timedelta(days=1)].mean()
back = u[fee:][u[fee:] <= u_base].index.min()
m["unity_2023"] = {
    "godot_sep2025_vs_year_before_fee": round(post_g.mean() / pre_g.mean(), 1),
    "godot_to_unity_ratio_before": round(r[pre_g.index].mean(), 2),
    "godot_to_unity_ratio_sep2025": round(r[post_g.index].mean(), 2),
    "weeks_until_unity_back_to_baseline": round((back - fee).days / 7),
}

os.makedirs("outputs", exist_ok=True)
json.dump(m, open("outputs/trend_metrics.json", "w"), indent=2)
print(json.dumps(m, indent=2))
