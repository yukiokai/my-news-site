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
    # Bing News format
    if hasattr(entry, "news_image"):
        return entry.news_image
    
    # media:thumbnail (some standard RSS)
    thumbnails = getattr(entry, "media_thumbnail", None)
    if thumbnails and isinstance(thumbnails, list) and thumbnails[0].get("url"):
        return thumbnails[0]["url"]

    # enclosures
    for enc in getattr(entry, "enclosures", []):
        ctype = enc.get("type", "")
        if ctype.startswith("image"):
            return enc.get("href", enc.get("url", ""))

    return ""


def news_url(query, mkt="ja-JP"):
    encoded = urllib.parse.quote(query)
    return f"https://www.bing.com/news/search?q={encoded}&format=rss&mkt={mkt}"


# ─── 国内カテゴリ ────────────────────────────────────────────────
DOMESTIC_CATEGORIES = {
    "🚁 ドローン・UAV動向": [
        news_url("ドローン UAV", "ja-JP"),
        news_url("無人航空機 飛行", "ja-JP"),
        news_url("ドローン 測量 OR 点検", "ja-JP"),
        news_url("ドローン 開発", "ja-JP"),
    ],
    "📡 LiDAR・SLAM・点群技術": [
        news_url("LiDAR 点群", "ja-JP"),
        news_url("SLAM 自己位置推定", "ja-JP"),
        news_url("三次元計測 OR 3Dスキャン", "ja-JP"),
        news_url("レーザースキャナー 測量", "ja-JP"),
    ],
    "📐 測量・建設DX・i-Construction": [
        news_url("測量 DX 建設", "ja-JP"),
        news_url("i-Construction BIM CIM", "ja-JP"),
        news_url("インフラ点検 土木", "ja-JP"),
    ],
    "💰 補助金・予算・規制情報": [
        news_url("ドローン 補助金 OR 改正", "ja-JP"),
        news_url("測量 補助金 OR 国土交通省", "ja-JP"),
        news_url("建設 DX 補助金", "ja-JP"),
    ],
    "🏗️ 建設コンサルタント・インフラ": [
        news_url("建設コンサルタント", "ja-JP"),
        news_url("インフラ 点検 維持管理", "ja-JP"),
        news_url("国土地理院 測量 地図", "ja-JP"),
    ],
}

# ─── 海外カテゴリ ───────────────────────────────────────────────
INTERNATIONAL_CATEGORIES = {
    "🚁 Drone & UAV Technology": [
        news_url("UAV LiDAR survey mapping", "en-US"),
        news_url("drone autonomous flight", "en-US"),
        news_url("commercial drone industry", "en-US"),
    ],
    "📡 LiDAR, SLAM & 3D Technology": [
        news_url("LiDAR point cloud 3D mapping", "en-US"),
        news_url("SLAM Simultaneous Localization and Mapping", "en-US"),
        news_url("3D scanning survey technology", "en-US"),
    ],
    "🗺️ Geospatial & Surveying Tech": [
        news_url("geospatial technology surveying", "en-US"),
        news_url("BIM GIS digital twin", "en-US"),
    ],
    "🤖 Autonomous Systems & Robotics": [
        news_url("autonomous drone robotics inspection", "en-US"),
        news_url("mobile robotics navigation", "en-US"),
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

                    source_name = getattr(entry, "news_source", "")
                    if not source_name:
                        src = getattr(entry, "source", None)
                        if src and isinstance(src, dict):
                            source_name = src.get("title", "")
                    if not source_name:
                        source_name = getattr(feed.feed, "title", "Bing News")

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

    domestic_count = sum(len(v) for v in domestic_data.values())
    intl_count = sum(len(v) for v in international_data.values())

    html_content = template.render(
        domestic_data=domestic_data,
        international_data=international_data,
        domestic_count=domestic_count,
        intl_count=intl_count,
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
