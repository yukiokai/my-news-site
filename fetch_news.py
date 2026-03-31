import time
import re
import urllib.parse
import pytz
from datetime import datetime

try:
    import feedparser
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("Dependencies not met. Please run: pip install -r requirements.txt")
    exit(1)


def format_date(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            jst = pytz.timezone("Asia/Tokyo")
            dt = datetime.fromtimestamp(time.mktime(parsed), tz=pytz.utc).astimezone(jst)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    raw = entry.get("published") or entry.get("updated") or ""
    return raw[:16] if len(raw) > 16 else raw


def get_timestamp(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return time.mktime(parsed)
        except Exception:
            pass
    return 0


def get_image_url(entry):
    """Extract best-effort image URL from a feed entry."""
    # media:thumbnail (most common in Google News)
    thumbnails = getattr(entry, "media_thumbnail", None)
    if thumbnails and isinstance(thumbnails, list) and thumbnails[0].get("url"):
        return thumbnails[0]["url"]

    # media:content
    media_content = getattr(entry, "media_content", None)
    if media_content and isinstance(media_content, list):
        for m in media_content:
            if m.get("url") and m.get("medium") in ("image", None):
                return m["url"]

    # enclosures
    for enc in getattr(entry, "enclosures", []):
        ctype = enc.get("type", "")
        if ctype.startswith("image"):
            return enc.get("href", enc.get("url", ""))

    # img tag inside summary
    summary = entry.get("summary", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
    if m:
        return m.group(1)

    return ""


def google_news_url(query, lang="ja", country="JP"):
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl={lang}&gl={country}&ceid={country}:{lang}"


# ─── 国内カテゴリ ────────────────────────────────────────────────
DOMESTIC_CATEGORIES = {
    "🚁 ドローン・UAV動向": [
        google_news_url("ドローン UAV"),
        google_news_url("無人航空機 飛行"),
        google_news_url("ドローン 測量 OR 点検 OR 物流"),
        google_news_url("ドローン 新技術 OR 開発"),
    ],
    "📡 LiDAR・SLAM・点群技術": [
        google_news_url("LiDAR 点群"),
        google_news_url("SLAM 自己位置推定"),
        google_news_url("三次元計測 OR 3Dスキャン"),
        google_news_url("レーザースキャナー 測量"),
    ],
    "📐 測量・建設DX・i-Construction": [
        google_news_url("測量 DX 建設"),
        google_news_url("i-Construction BIM CIM"),
        google_news_url("インフラ点検 ドローン 土木"),
        google_news_url("建設 デジタル化 OR ICT"),
    ],
    "💰 補助金・予算・規制情報": [
        google_news_url("ドローン 補助金 OR 予算 OR 規制"),
        google_news_url("測量 補助金 OR 国土交通省"),
        google_news_url("建設 DX 補助金 OR 助成金"),
        google_news_url("無人機 規制 OR 法改正"),
    ],
    "🏗️ 建設コンサルタント・インフラ": [
        google_news_url("建設コンサルタント"),
        google_news_url("インフラ 点検 維持管理"),
        google_news_url("国土地理院 測量 地図"),
        google_news_url("橋梁 OR トンネル 点検 DX"),
    ],
}

# ─── 海外カテゴリ ───────────────────────────────────────────────
INTERNATIONAL_CATEGORIES = {
    "🚁 Drone & UAV Technology": [
        google_news_url("UAV LiDAR survey mapping", "en", "US"),
        google_news_url("drone autonomous flight technology", "en", "US"),
        google_news_url("unmanned aerial vehicle inspection infrastructure", "en", "US"),
        google_news_url("commercial drone industry news", "en", "US"),
    ],
    "📡 LiDAR, SLAM & 3D Technology": [
        google_news_url("LiDAR point cloud 3D mapping technology", "en", "US"),
        google_news_url("SLAM simultaneous localization mapping robotics", "en", "US"),
        google_news_url("3D scanning survey technology industry", "en", "US"),
        google_news_url("mobile mapping lidar autonomous", "en", "US"),
    ],
    "🗺️ Geospatial & Surveying Tech": [
        google_news_url("geospatial technology surveying innovation", "en", "US"),
        google_news_url("BIM GIS construction digital twin", "en", "US"),
        google_news_url("remote sensing satellite drone mapping", "en", "US"),
    ],
    "🤖 Autonomous Systems & Robotics": [
        google_news_url("autonomous drone robotics industry 2025", "en", "US"),
        google_news_url("mobile robotics SLAM navigation research", "en", "US"),
        google_news_url("robot autonomous inspection infrastructure", "en", "US"),
    ],
}


def fetch_category_data(categories, max_per_category=15):
    news_data = {}
    seen_links = set()

    for category, urls in categories.items():
        category_news = []
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:12]:
                    link = entry.get("link", "")
                    if link in seen_links:
                        continue
                    seen_links.add(link)

                    source_name = ""
                    src = getattr(entry, "source", None)
                    if src and isinstance(src, dict):
                        source_name = src.get("title", "")
                    if not source_name:
                        source_name = getattr(feed.feed, "title", "Google News")

                    category_news.append({
                        "title": entry.title,
                        "link": link,
                        "source": source_name,
                        "date": format_date(entry),
                        "timestamp": get_timestamp(entry),
                        "image": get_image_url(entry),
                        "summary": re.sub(r'<[^>]+>', '', entry.get("summary", ""))[:100],
                    })
            except Exception as e:
                print(f"  [WARN] Error fetching {url}: {e}")

        category_news.sort(key=lambda x: x["timestamp"], reverse=True)
        news_data[category] = category_news[:max_per_category]

    return news_data


def generate_html(domestic_data, international_data):
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("template.html")

    jst = pytz.timezone("Asia/Tokyo")
    update_time = datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S")

    html_content = template.render(
        domestic_data=domestic_data,
        international_data=international_data,
        update_time=update_time,
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Generated index.html at {update_time} JST.")


if __name__ == "__main__":
    print("Fetching domestic news...")
    domestic = fetch_category_data(DOMESTIC_CATEGORIES, max_per_category=15)

    print("Fetching international news...")
    international = fetch_category_data(INTERNATIONAL_CATEGORIES, max_per_category=15)

    print("Generating HTML...")
    generate_html(domestic, international)
    print("Done!")
