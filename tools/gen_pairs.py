"""Generates the time-difference pages: one per city pair, a hub page and sitemap.xml.

    python3 tools/gen_pairs.py

Every fact on a page is computed here from the IANA time-zone rules on this machine (the tzdata
version is printed on the page), so nothing is hand-written per pair. The live grid on each page
uses the visitor's browser rules instead (time-difference/grid.js).
"""
import datetime as dt
import html
import json
import os
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "time-difference"
SITE = "https://csjobeck.github.io/hourgrid-site"
APP = "https://apps.apple.com/app/id6819993325"
YEAR = 2027
MON_FRI, SUN_THU = [1, 2, 3, 4, 5], [0, 1, 2, 3, 4]

# slug: (display name, IANA zone, working week)
CITIES = {
    "london": ("London", "Europe/London", MON_FRI),
    "new-york": ("New York", "America/New_York", MON_FRI),
    "san-francisco": ("San Francisco", "America/Los_Angeles", MON_FRI),
    "chicago": ("Chicago", "America/Chicago", MON_FRI),
    "toronto": ("Toronto", "America/Toronto", MON_FRI),
    "vancouver": ("Vancouver", "America/Vancouver", MON_FRI),
    "mexico-city": ("Mexico City", "America/Mexico_City", MON_FRI),
    "sao-paulo": ("São Paulo", "America/Sao_Paulo", MON_FRI),
    "dublin": ("Dublin", "Europe/Dublin", MON_FRI),
    "paris": ("Paris", "Europe/Paris", MON_FRI),
    "berlin": ("Berlin", "Europe/Berlin", MON_FRI),
    "amsterdam": ("Amsterdam", "Europe/Amsterdam", MON_FRI),
    "copenhagen": ("Copenhagen", "Europe/Copenhagen", MON_FRI),
    "stockholm": ("Stockholm", "Europe/Stockholm", MON_FRI),
    "madrid": ("Madrid", "Europe/Madrid", MON_FRI),
    "warsaw": ("Warsaw", "Europe/Warsaw", MON_FRI),
    "tel-aviv": ("Tel Aviv", "Asia/Jerusalem", SUN_THU),
    "riyadh": ("Riyadh", "Asia/Riyadh", SUN_THU),
    "dubai": ("Dubai", "Asia/Dubai", MON_FRI),
    "india": ("India", "Asia/Kolkata", MON_FRI),
    "singapore": ("Singapore", "Asia/Singapore", MON_FRI),
    "hong-kong": ("Hong Kong", "Asia/Hong_Kong", MON_FRI),
    "china": ("China", "Asia/Shanghai", MON_FRI),
    "philippines": ("Philippines", "Asia/Manila", MON_FRI),
    "tokyo": ("Tokyo", "Asia/Tokyo", MON_FRI),
    "sydney": ("Sydney", "Australia/Sydney", MON_FRI),
    "auckland": ("Auckland", "Pacific/Auckland", MON_FRI),
    "johannesburg": ("Johannesburg", "Africa/Johannesburg", MON_FRI),
    "lagos": ("Lagos", "Africa/Lagos", MON_FRI),
}

HUBS = ["london", "new-york", "san-francisco", "chicago", "toronto", "paris", "berlin", "dubai",
        "india", "singapore", "tokyo", "sydney"]
EXTRA = [
    ("copenhagen", "london"), ("copenhagen", "new-york"), ("copenhagen", "san-francisco"), ("copenhagen", "india"),
    ("stockholm", "new-york"), ("stockholm", "london"), ("amsterdam", "new-york"), ("amsterdam", "san-francisco"),
    ("dublin", "new-york"), ("dublin", "san-francisco"), ("madrid", "new-york"), ("warsaw", "london"),
    ("warsaw", "new-york"), ("tel-aviv", "new-york"), ("tel-aviv", "london"), ("riyadh", "london"),
    ("riyadh", "new-york"), ("philippines", "new-york"), ("philippines", "sydney"), ("philippines", "london"),
    ("china", "new-york"), ("china", "london"), ("hong-kong", "new-york"), ("hong-kong", "london"),
    ("mexico-city", "new-york"), ("sao-paulo", "new-york"), ("sao-paulo", "london"), ("vancouver", "london"),
    ("auckland", "london"), ("auckland", "sydney"), ("johannesburg", "london"), ("lagos", "london"),
]
PAIRS = [(a, b) for i, a in enumerate(HUBS) for b in HUBS[i + 1:]] + EXTRA

WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def offset_hours(tz, when):
    return when.astimezone(ZoneInfo(tz)).utcoffset().total_seconds() / 3600


def days(year):
    d = dt.date(year, 1, 1)
    while d.year == year:
        yield d
        d += dt.timedelta(days=1)


def noon(d):
    return dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone.utc)


def segments(a_tz, b_tz, year):
    """[(first day, last day, B minus A in hours)] through the year."""
    out = []
    for d in days(year):
        diff = offset_hours(b_tz, noon(d)) - offset_hours(a_tz, noon(d))
        if out and out[-1][2] == diff:
            out[-1][1] = d
        else:
            out.append([d, d, diff])
    return out


def observes_dst(tz, year):
    return len({offset_hours(tz, noon(d)) for d in days(year)}) > 1


def northern(tz, year):
    return offset_hours(tz, noon(dt.date(year, 7, 1))) > offset_hours(tz, noon(dt.date(year, 1, 1)))


def amount(hours):
    h = abs(hours)
    whole, half = int(h), h - int(h)
    frac = {0.5: "½", 0.25: "¼", 0.75: "¾"}.get(round(half, 2), "")
    if whole == 0 and frac:
        return f"{frac} hour"
    return f"{whole}{frac} hour{'s' if h != 1 else ''}"


def relation(diff, a, b):
    if diff == 0:
        return f"{b} and {a} are on the same time"
    return f"{b} is {amount(diff)} {'ahead of' if diff > 0 else 'behind'} {a}"


def clock(hours):
    """A time of day from hours since midnight, e.g. 9.5 -> '9:30 am'."""
    hours %= 24
    h, m = int(hours), round((hours - int(hours)) * 60)
    suffix = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}" if m else f"{h12} {suffix}"


def fmt_date(d):
    return f"{d.day} {d.strftime('%B')}"


def overlap(diff):
    """Hours (in A's day) when both are inside 9–5, for a B−A difference; may wrap a day."""
    best = None
    for shift in (-24, 0, 24):
        lo, hi = max(9, 9 - diff + shift), min(17, 17 - diff + shift)
        if hi > lo and (best is None or hi - lo > best[1] - best[0]):
            best = (lo, hi)
    return best


def page(a, b):
    an, atz, awk = CITIES[a]
    bn, btz, bwk = CITIES[b]
    segs = segments(atz, btz, YEAR)
    usual = Counter({s[2]: 0 for s in segs})
    for s in segs:
        usual[s[2]] += (s[1] - s[0]).days + 1
    main = usual.most_common(1)[0][0]
    minority_days = sum(n for diff, n in usual.items() if diff != main)

    # Lede: a single sentence that stays true all year; the table below has the dates.
    values = sorted(usual, key=abs)
    if len(usual) == 1:
        lede = f"{relation(main, an, bn)} all year."
    elif minority_days <= 60:
        lede = f"{relation(main, an, bn)} for most of the year."
    elif 0 in values:
        other = [v for v in values if v != 0][-1]
        lede = (f"{bn} is on the same time as {an} or {amount(other)} {'ahead' if other > 0 else 'behind'}, "
                f"depending on the time of year.")
    elif all(v > 0 for v in values) or all(v < 0 for v in values):
        side = "ahead of" if values[0] > 0 else "behind"
        joiner = "or" if len(values) == 2 else "to"
        lo, hi = amount(values[0]), amount(values[-1])
        lo = lo.replace(" hours", "").replace(" hour", "")
        lede = f"{bn} is {'between ' if len(values) > 2 else ''}{lo} {'and' if len(values) > 2 else joiner} {hi} {side} {an}, depending on the time of year."
    else:
        lede = f"The difference between {an} and {bn} changes through the year; the table below has the dates."

    # Why it changes.
    a_dst, b_dst = observes_dst(atz, YEAR), observes_dst(btz, YEAR)
    if a_dst and b_dst:
        if northern(atz, YEAR) != northern(btz, YEAR):
            why = (f"Both use daylight saving time, but on opposite sides of the equator: when one moves "
                   f"its clocks forward, the other moves them back.")
        elif len(usual) > 1:
            why = (f"Both {an} and {bn} use daylight saving time, but they change their clocks on different "
                   f"dates, so for a few weeks a year the difference is one hour off.")
        else:
            why = f"Both {an} and {bn} use daylight saving time and change on the same dates."
    elif a_dst or b_dst:
        mover, still = (an, bn) if a_dst else (bn, an)
        why = f"{mover} uses daylight saving time and {still} doesn't, so the difference changes twice a year."
    else:
        why = f"Neither {an} nor {bn} uses daylight saving time, so the difference never changes."

    rows = "".join(
        f"<tr><td>{fmt_date(s[0])} – {fmt_date(s[1])}</td><td>{html.escape(relation(s[2], an, bn))}</td></tr>"
        for s in segs)

    # Working hours on a typical day.
    ov = overlap(main)
    if ov:
        lo, hi = ov
        meet = (f"On a typical workday both are at work (9 to 5) for {amount(hi - lo)}: "
                f"{clock(lo)} to {clock(hi)} in {an} is {clock(lo + main)} to {clock(hi + main)} in {bn}.")
    else:
        meet = (f"Their 9-to-5 days don't overlap. The least awkward times are usually early or late: "
                f"8 am in {an} is {clock(8 + main)} in {bn}, and 6 pm in {an} is {clock(18 + main)} in {bn}.")

    week = ""
    if awk != bwk:
        sun_thu, mon_fri = (an, bn) if awk == SUN_THU else (bn, an)
        week = (f"<h2>Working weeks</h2><p>{sun_thu} works Sunday to Thursday and {mon_fri} Monday to Friday, "
                f"so only Monday to Thursday are shared working days. Friday is a day off in {sun_thu}, "
                f"and Sunday is a working day there.</p>")

    related = []
    for x, y in PAIRS:
        if (x, y) != (a, b) and {a, b} & {x, y}:
            related.append(f'<a href="../{x}-{y}/">{CITIES[x][0]} and {CITIES[y][0]}</a>')
    related = related[:10]

    data = json.dumps([
        {"name": an, "tz": atz, "workdays": awk, "opens": 9, "closes": 17},
        {"name": bn, "tz": btz, "workdays": bwk, "opens": 9, "closes": 17},
    ])
    title = f"{an} and {bn} time difference and best meeting time"
    desc = f"{lede} See the hours side by side, when both are at work, and every daylight saving change in {YEAR}."
    url = f"{SITE}/time-difference/{a}-{b}/"
    tzdata = (Path("/usr/share/zoneinfo/+VERSION").read_text().strip()
              if Path("/usr/share/zoneinfo/+VERSION").exists() else "system")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} | Hourgrid</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@700&family=IBM+Plex+Sans:wght@400;600&display=swap">
<link rel="stylesheet" href="../../style.css">
<link rel="icon" href="../../icon.png">
<meta name="apple-itunes-app" content="app-id=6819993325">
</head>
<body>
<header><a href="../../"><img src="../../icon.png" alt=""><span>Hourgrid</span></a></header>
<main>
  <h1>{html.escape(an)} and {html.escape(bn)}: time difference and best meeting time</h1>
  <p class="lede">{html.escape(lede)}</p>

  <section id="live" class="grid live" data-cities='{html.escape(data)}'>
    <div class="daynav">
      <button type="button" data-prev aria-label="Previous day">‹</button>
      <strong data-day></strong>
      <button type="button" data-next aria-label="Next day">›</button>
      <button type="button" data-today>Today</button>
      <label>Date <input type="date" data-date></label>
    </div>
    <div class="scroll"><table></table></div>
    <div class="legend"><span><i class="o"></i>At work (9 to 5)</span><span><i class="d"></i>Day</span><span><i class="e"></i>Morning or evening</span><span><i class="n"></i>Night</span></div>
    <p data-best></p>
    <p class="note" data-now></p>
    <noscript><p>The live grid needs JavaScript. The facts below work without it.</p></noscript>
  </section>

  <h2>Best time to meet</h2>
  <p>{html.escape(meet)}</p>

  <h2>Daylight saving time</h2>
  <p>{html.escape(why)}</p>
  <table class="periods"><caption>{html.escape(an)} and {html.escape(bn)} in {YEAR}</caption>
    <tr><th>Dates</th><th>Difference</th></tr>{rows}</table>
  {week}

  <h2>Plan with more than two cities</h2>
  <p>Hourgrid puts every city you work with side by side on your iPhone or iPad, with each office's own opening hours and working days, and shows the hour that suits everyone. Free for three places; Pro is one price, no subscription.</p>
  <a class="store" href="{APP}"><span><small>Download on the</small>App Store</span></a>

  <h2>Related</h2>
  <p class="related">{" · ".join(related)} · <a href="../">All cities</a></p>
  <p class="note">Computed from the IANA time-zone rules (tzdata {tzdata}). The live grid uses your browser's own rules and your local {"12-hour or 24-hour"} clock setting.</p>
</main>
<footer>© 2026 Christian Sjøbeck · <a href="../../">Hourgrid</a> · <a href="../../privacy/">Privacy</a></footer>
<script src="../grid.js" defer></script>
</body>
</html>
"""


def hub():
    groups = {}
    for a, b in PAIRS:
        groups.setdefault(a, []).append(b)
    items = "".join(
        f"<h3>{CITIES[a][0]}</h3><p>" + " · ".join(f'<a href="{a}-{b}/">{CITIES[a][0]} and {CITIES[b][0]}</a>' for b in bs) + "</p>"
        for a, bs in groups.items())
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Time difference between cities and best meeting times | Hourgrid</title>
<meta name="description" content="Time differences and the best meeting times for {len(PAIRS)} city pairs, with every daylight saving change and a live hour grid.">
<link rel="canonical" href="{SITE}/time-difference/">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@700&family=IBM+Plex+Sans:wght@400;600&display=swap">
<link rel="stylesheet" href="../style.css">
<link rel="icon" href="../icon.png">
<meta name="apple-itunes-app" content="app-id=6819993325">
</head>
<body>
<header><a href="../"><img src="../icon.png" alt=""><span>Hourgrid</span></a></header>
<main>
  <h1>Time difference between cities</h1>
  <p class="lede">The time difference and the best hour to meet for {len(PAIRS)} city pairs, including the weeks when daylight saving makes it change.</p>
  {items}
  <a class="store" href="{APP}"><span><small>Download on the</small>App Store</span></a>
</main>
<footer>© 2026 Christian Sjøbeck · <a href="../">Hourgrid</a> · <a href="../privacy/">Privacy</a></footer>
</body>
</html>
"""


def main():
    OUT.mkdir(exist_ok=True)
    for a, b in PAIRS:
        d = OUT / f"{a}-{b}"
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(page(a, b))
    (OUT / "index.html").write_text(hub())
    urls = [f"{SITE}/", f"{SITE}/time-buddy-alternative/", f"{SITE}/time-difference/"] + \
           [f"{SITE}/time-difference/{a}-{b}/" for a, b in PAIRS]
    today = dt.date.today().isoformat()
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    print(f"{len(PAIRS)} pair pages, hub and sitemap ({len(urls)} URLs)")


if __name__ == "__main__":
    main()
