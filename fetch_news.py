import time
import re
import urllib.parse
import pytz
import difflib
from datetime import datetime

try:
    import feedparser
    from jinja2 import Environment, FileSystemLoader
    from deep_translator import GoogleTranslator
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
    """Extract best-effort image URL from a feed entry. Optimized for Bing quality."""
    url = ""
    # Bing News format
    if hasattr(entry, "news_image"):
        url = entry.news_image
    else:
        # media:thumbnail (some standard RSS)
        thumbnails = getattr(entry, "media_thumbnail", None)
        if thumbnails and isinstance(thumbnails, list) and thumbnails[0].get("url"):
            url = thumbnails[0]["url"]
        else:
            # enclosures
            for enc in getattr(entry, "enclosures", []):
                ctype = enc.get("type", "")
                if ctype.startswith("image"):
                    url = enc.get("href", enc.get("url", ""))
                    break
    
    # Improve Bing image quality if it's a Bing thumbnail URL
    if url and "bing.com/th?" in url:
        # Clean up existing parameters to prevent resolution limiting
        base_url = url.split('&')[0] if '&' in url else url
        # Use w=1200 for higher resolution, and ensure c=14 for better scaling
        url = f"{base_url}&w=1200&h=675&c=14&rs=2&pid=News"
        
    return url


def news_url(query, mkt="ja-JP"):
    encoded = urllib.parse.quote(query)
    return f"https://www.bing.com/news/search?q={encoded}&format=rss&mkt={mkt}"


# ─── 国内カテゴリ ────────────────────────────────────────────────
# Bing RSSのOR検索挙動が不安定なため、個別のキーワードリストとして構成
DOMESTIC_CATEGORIES = {
    "🚁 ドローン・UAV動向": [
        news_url("ドローン", "ja-JP"),
        news_url("UAV", "ja-JP"),
        news_url("無人航空機", "ja-JP"),
        news_url("ドローン 測量", "ja-JP"),
        news_url("ドローン 点検", "ja-JP"),
    ],
    "📡 LiDAR・SLAM・点群技術": [
        news_url("LiDAR", "ja-JP"),
        news_url("SLAM", "ja-JP"),
        news_url("高精度三次元地図", "ja-JP"),
        news_url("自己位置推定", "ja-JP"),
        news_url("3Dスキャン", "ja-JP"),
    ],
    "📐 測量・建設DX・i-Construction": [
        news_url("建設DX", "ja-JP"),
        news_url("i-Construction", "ja-JP"),
        news_url("BIM/CIM", "ja-JP"),
        news_url("国土交通省 測量", "ja-JP"),
        news_url("インフラ点検", "ja-JP"),
    ],
    "💰 補助金・予算・規制情報": [
        news_url("ドローン 補助金", "ja-JP"),
        news_url("ドローン 規制", "ja-JP"),
        news_url("ドローン 法律", "ja-JP"),
        news_url("ドローン 登録", "ja-JP"),
    ],
    "🏗️ 建設コンサルタント・インフラ": [
        news_url("建設コンサルタント", "ja-JP"),
        news_url("インフラ 維持管理", "ja-JP"),
        news_url("国土地理院", "ja-JP"),
    ],
}

# ─── 海外カテゴリ ───────────────────────────────────────────────
INTERNATIONAL_CATEGORIES = {
    "🚁 Drone & UAV Technology": [
        news_url("drone", "en-US"),
        news_url("UAV", "en-US"),
        news_url("UAS", "en-US"),
        news_url("autonomous flight", "en-US"),
        news_url("drone inspection", "en-US"),
    ],
    "📡 LiDAR, SLAM & 3D Technology": [
        news_url("LiDAR", "en-US"),
        news_url("SLAM technology", "en-US"),
        news_url("point cloud mapping", "en-US"),
        news_url("3D scanning", "en-US"),
    ],
    "🗺️ Geospatial & Surveying Tech": [
        news_url("geospatial industry", "en-US"),
        news_url("surveying technology", "en-US"),
        news_url("digital twin drone", "en-US"),
    ],
    "🤖 Autonomous Systems & Robotics": [
        news_url("autonomous robotics", "en-US"),
        news_url("mobile robotics", "en-US"),
        news_url("autonomous navigation", "en-US"),
    ],
}


def is_similar_title(new_title, existing_titles, threshold=0.85):
    """
    タイトルの類似度判定。
    閾値を0.85に設定することで、類似トピックでも別メディアの記事であれば許可するように緩和。
    """
    for et in existing_titles:
        if difflib.SequenceMatcher(None, new_title, et).ratio() > threshold:
            return True
    return False


def fetch_category_data(categories, max_per_category=15):
    news_data = {}
    seen_links = set()
    seen_titles = set()

    for category, urls in categories.items():
        category_news = []
        for url in urls:
            try:
                # 取得を試行
                feed = feedparser.parse(url)
                # 1つのキーワードにつき上位10件程度を見る
                for entry in feed.entries[:10]:
                    link = entry.get("link", "")
                    if link in seen_links:
                        continue
                    
                    title = entry.title
                    # タイトルが「No Image」等の不適切なものはスキップ
                    if not title or "no image" in title.lower():
                        continue

                    # Deduplicate by title similarity
                    if is_similar_title(title, seen_titles):
                        continue

                    seen_links.add(link)
                    seen_titles.add(title)

                    source_name = getattr(entry, "news_source", "")
                    if not source_name:
                        src = getattr(entry, "source", None)
                        if src and isinstance(src, dict):
                            source_name = src.get("title", "")
                    if not source_name:
                        source_name = getattr(feed.feed, "title", "Bing News")

                    category_news.append({
                        "title": title,
                        "link": link,
                        "source": source_name,
                        "date": format_date(entry),
                        "timestamp": get_timestamp(entry),
                        "image": get_image_url(entry),
                        "summary": re.sub(r'<[^>]+>', '', entry.get("summary", ""))[:120],
                    })
            except Exception as e:
                print(f"  [WARN] Error fetching {url}: {e}")

        # 新しい順にソートして最大15件
        category_news.sort(key=lambda x: x["timestamp"], reverse=True)
        news_data[category] = category_news[:max_per_category]

    return news_data


def generate_html(domestic_data, international_data, international_translated):
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("template.html")

    jst = pytz.timezone("Asia/Tokyo")
    update_time = datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S")

    domestic_count = sum(len(v) for v in domestic_data.values())
    intl_count = sum(len(v) for v in international_data.values())

    html_content = template.render(
        domestic_data=domestic_data,
        international_data=international_data,
        international_translated=international_translated,
        domestic_count=domestic_count,
        intl_count=intl_count,
        update_time=update_time,
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Generated index.html at {update_time} JST.")


if __name__ == "__main__":
    print("Fetching domestic news...")
    domestic = fetch_category_data(DOMESTIC_CATEGORIES, max_per_category=10)

    print("Fetching international news...")
    # 海外ニュースは翻訳負荷を考慮し、トップ5件ずつに限定（翻訳精度維持のため）
    international = fetch_category_data(INTERNATIONAL_CATEGORIES, max_per_category=8)
    
    print("Translating international news...")
    international_translated = {}
    translator = GoogleTranslator(source='auto', target='ja')
    
    for category, items in international.items():
        translated_items = []
        for item in items:
            new_item = item.copy()
            # 翻訳に失敗しても元データを維持
            try:
                # タイトル翻訳 (最大文字数制限を意識)
                if item["title"]:
                    new_item["title"] = translator.translate(item["title"])
                
                # サマリー翻訳
                if item.get("summary"):
                    # 翻訳後のサマリーは少し長めに
                    new_item["summary"] = translator.translate(item["summary"])
                
                time.sleep(0.3) # 負荷軽減のためのウェイト
            except Exception as e:
                print(f"  [WARN] Translation failed for {item['title'][:20]}: {e}")
                # 失敗時は英語をそのまま表示
                pass
            
            translated_items.append(new_item)
        international_translated[category] = translated_items

    print("Generating HTML...")
    generate_html(domestic, international, international_translated)
    print("Done!")
