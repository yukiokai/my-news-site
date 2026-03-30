import time
from datetime import datetime
import urllib.parse
import pytz

try:
    import feedparser
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("Dependencies not met. Please run: pip install -r requirements.txt")
    exit(1)

def format_date(entry):
    """Parse and format the publication date from a feed entry."""
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

def google_news_url(query):
    """Build a Google News RSS URL for a Japanese keyword query."""
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"

# --- TerraDrone 特化カテゴリ ---
# 各カテゴリに複数の検索クエリを設定
CATEGORIES = {
    "🚁 ドローン・UAV動向": [
        google_news_url("ドローン UAV"),
        google_news_url("無人航空機 飛行"),
        google_news_url("drone LiDAR 測量"),
    ],
    "📡 LiDAR・SLAM・点群技術": [
        google_news_url("LiDAR 点群"),
        google_news_url("SLAM 自己位置推定"),
        google_news_url("三次元計測 測量"),
    ],
    "📐 測量・建設DX・i-Construction": [
        google_news_url("測量 DX"),
        google_news_url("i-Construction BIM CIM"),
        google_news_url("インフラ点検 ドローン"),
    ],
    "💰 補助金・予算・規制情報": [
        google_news_url("ドローン 補助金 OR 予算 OR 規制"),
        google_news_url("測量 補助金 OR 国土交通省"),
        google_news_url("建設 DX 補助金"),
    ],
    "🏗️ 建設コンサルタント・インフラ": [
        google_news_url("建設コンサルタント"),
        google_news_url("インフラ 点検 維持管理"),
        google_news_url("地図 測量 国土地理院"),
    ],
}

def fetch_feed_data():
    news_data = {}
    for category, urls in CATEGORIES.items():
        category_news = []
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:8]:
                    timestamp = get_timestamp(entry)
                    source_name = getattr(entry, "source", {}).get("title", "Google News")

                    category_news.append({
                        "title": entry.title,
                        "link": entry.link,
                        "source": source_name,
                        "date": format_date(entry),
                        "timestamp": timestamp
                    })
            except Exception as e:
                print(f"Error fetching {url}: {e}")
        
        category_news.sort(key=lambda x: x["timestamp"], reverse=True)
        news_data[category] = category_news[:10]
        
    return news_data

def generate_html(news_data):
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('template.html')
    
    jst = pytz.timezone('Asia/Tokyo')
    update_time = datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S')
    
    html_content = template.render(
        news_data=news_data,
        update_time=update_time
    )
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Generated index.html successfully at {update_time} JST.")

if __name__ == "__main__":
    print("Fetching news feeds...")
    data = fetch_feed_data()
    print("Generating HTML...")
    generate_html(data)
    print("Done!")
