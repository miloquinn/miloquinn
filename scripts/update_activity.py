"""Render profile graphics from the anonymous, public GitHub contribution calendar."""

from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COLORS = ["#202D36", "#18574E", "#227E6E", "#38B59A", "#76E4C5"]
FONT = "Arial, Helvetica, sans-serif"


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.counts = {}
        self.tip = None
        self.tip_text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("data-date"):
            self.cells[attrs["id"]] = (
                date.fromisoformat(attrs["data-date"]),
                int(attrs["data-level"]),
            )
        if tag == "tool-tip":
            self.tip = attrs.get("for")
            self.tip_text = ""

    def handle_data(self, data):
        if self.tip:
            self.tip_text += data

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tip:
            text = self.tip_text.strip()
            match = re.match(r"([\d,]+) contributions? on ", text)
            if match:
                self.counts[self.tip] = int(match[1].replace(",", ""))
            elif text.startswith("No contributions on "):
                self.counts[self.tip] = 0
            else:
                raise ValueError("Unexpected public contribution tooltip format")
            self.tip = None


def text(x, y, value, size=16, color="#B8C8CE", weight=400):
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
        f'font-weight="{weight}">{escape(str(value))}</text>'
    )


def canvas(width, height, title, content):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-labelledby="title"><title id="title">{escape(title)}</title>'
        f'<rect width="{width}" height="{height}" rx="16" fill="#101B23"/>'
        f'<g font-family="{FONT}">{content}</g></svg>\n'
    )


def hero(compact=False):
    width, height = (480, 230) if compact else (900, 230)
    content = text(32, 73, "Milo / Origo", 48, "#F0F5F5", 700)
    content += text(32, 116, "Build things worth using.", 24, "#76E4C5", 500)
    content += text(32, 157, "Reading experiences. Open protocols.", 16)
    content += text(32, 181, "Tools that turn ideas into products.", 16)
    if not compact:
        content += '<path d="M604 80H827M604 80V156H827" fill="none" stroke="#315449" stroke-width="2"/>'
        for x, y, label in [(604, 80, "READER"), (827, 80, "PROTOCOL"), (827, 156, "TOOLS")]:
            content += f'<circle cx="{x}" cy="{y}" r="5" fill="#76E4C5"/>'
            content += text(x - (80 if x > 800 else 0), y - 19, label, 12, "#B8C8CE", 600)
    return canvas(width, height, "Milo / Origo — Build things worth using.", content)


def activity(days, today, compact=False, recent_days=None):
    width, height = (480, 374) if compact else (900, 340)
    total = sum(n for _, n, _ in days)
    recent = [n for day, n, _ in (recent_days or days) if day >= today - timedelta(days=29)]
    active = sum(n > 0 for n in recent)
    run = longest = 0
    for _, count, _ in days:
        run = run + 1 if count else 0
        longest = max(longest, run)
    content = text(28, 39, "Always building.", 24, "#F0F5F5", 700)
    content += text(28, 62, f"Public GitHub activity / {today.year}", 13)
    metrics = [
        (f"{total:,}", f"contributions in {today.year}"),
        (f"{sum(recent):,}", "in the last 30 days"),
        (f"{active} / 30", "days active"),
        (f"{longest}", "day longest streak"),
    ]
    for i, (value, label) in enumerate(metrics):
        x = 28 + (i % 2) * 228 if compact else 28 + i * 219
        y = 106 + (i // 2) * 76 if compact else 110
        content += text(x, y, value, 30, "#76E4C5", 700)
        content += text(x, y + 22, label, 12)
    step = 8 if compact else 16
    start_y = 254 if compact else 189
    jan1 = date(today.year, 1, 1)
    origin = jan1 - timedelta(days=(jan1.weekday() + 1) % 7)
    content += text(28, start_y - 13, "Jan", 11)
    content += text(28 + 26 * step, start_y - 13, "Jul", 11)
    content += text(28 + 49 * step, start_y - 13, "Dec", 11)
    calendar = {day: (count, level) for day, count, level in days}
    day = jan1
    while day.year == today.year:
        count, level = calendar.get(day, (0, 0))
        offset = (day - origin).days
        x = 28 + (offset // 7) * step
        y = start_y + (offset % 7) * step
        color = COLORS[level] if day <= today else "#17242D"
        label = f"{day.isoformat()}: {count} contributions" if day <= today else day.isoformat()
        content += (
            f'<rect x="{x}" y="{y}" width="{step - 2}" height="{step - 2}" '
            f'rx="{1 if compact else 3}" fill="{color}">'
            f'<title>{label}</title></rect>'
        )
        day += timedelta(days=1)
    content += text(28, height - 20, f"Updated {today.isoformat()} / github.com/miloquinn", 11)
    return canvas(width, height, "Milo's public GitHub contribution activity", content)


def fetch_calendar(today):
    request = Request(
        f"https://github.com/users/miloquinn/contributions?to={today.isoformat()}",
        headers={"User-Agent": "miloquinn-profile", "Accept": "text/html"},
    )
    with urlopen(request, timeout=30) as response:
        document = response.read().decode("utf-8")
    parser = CalendarParser()
    parser.feed(document)
    days = sorted(
        (day, parser.counts[key], level)
        for key, (day, level) in parser.cells.items()
        if date(today.year, 1, 1) <= day <= today
    )
    expected_days = (today - date(today.year, 1, 1)).days + 1
    if len(days) != expected_days or len({d for d, _, _ in days}) != expected_days:
        raise ValueError("Public calendar is incomplete; existing graphics preserved")
    if any(n < 0 or not 0 <= level <= 4 for _, n, level in days):
        raise ValueError("Invalid public contribution data")
    return days


def main():
    today = datetime.now(timezone(timedelta(hours=8))).date()
    days = fetch_calendar(today)
    recent_days = days
    if today.timetuple().tm_yday < 30:
        recent_days = fetch_calendar(date(today.year - 1, 12, 31)) + days
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    for compact in [False, True]:
        suffix = "-compact" if compact else ""
        (assets / f"hero{suffix}.svg").write_text(hero(compact), encoding="utf-8")
        (assets / f"activity{suffix}.svg").write_text(
            activity(days, today, compact, recent_days), encoding="utf-8"
        )
    print(f"Updated public contribution graphics for {today}: {sum(n for _, n, _ in days):,} contributions")


if __name__ == "__main__":
    main()
