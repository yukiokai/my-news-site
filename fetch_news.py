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
    import yfinance as yf
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
    
    # 2. Google News対策: summaryやdescription内のimgタグを探す
    if not url:
        summary = entry.get("summary", getattr(entry, "description", ""))
        img_match = re.search(r'<img[^>]+src=["\'](.*?)["\']', summary, re.IGNORECASE)
        if img_match:
            url = img_match.group(1)
            
    # 3. 究極の対策: 画像がない場合、リンク先のOGP画像(og:image)を直接スクレイピングして取得する
    if not url and hasattr(entry, "link"):
        try:
            import urllib.request
            req = urllib.request.Request(entry.link, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
            # GoogleNewsのリダイレクトを辿るためのタイムアウトを長めに(3秒)
            html = urllib.request.urlopen(req, timeout=3).read().decode('utf-8', errors='ignore')
            
            # meta property="og:image" content="..." または meta content="..." property="og:image" に対応
            match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](.*?)["\']|<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:image["\']', html, re.IGNORECASE)
            if match:
                url = match.group(1) or match.group(2)
        except Exception as e:
            # 取得失敗時は無視して次の処理へ
            pass

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

def google_news_url(query, hl="ja", gl="JP", ceid="JP:ja"):
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"

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
        news_url("LiDAR ドローン", "ja-JP"),
        news_url("SLAM ドローン", "ja-JP"),
        news_url("点群データ 測量", "ja-JP"),
        news_url("自己位置推定 ロボット", "ja-JP"),
        news_url("3Dモデル 測量", "ja-JP"),
    ],
    "📐 測量・建設DX・i-Construction": [
        news_url("建設DX", "ja-JP"),
        news_url("i-Construction", "ja-JP"),
        news_url("BIM/CIM", "ja-JP"),
        news_url("測量 ドローン", "ja-JP"),
        news_url("インフラ点検 ドローン", "ja-JP"),
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
    "🛠️ 測量機器・LiDAR・SLAM (新製品・メーカー動向)": [
        google_news_url("Trimble 測量 新製品 OR トリンブル"),
        google_news_url("ライカ ジオシステムズ"),
        google_news_url("Leica 測量スキャナ"),
        google_news_url("CHCNAV"),
        google_news_url("トプコン 新製品 OR 測量"),
        google_news_url("YellowScan"),
        google_news_url("FLIGHTS SCAN"),
        google_news_url("RIEGL LiDAR"),
        google_news_url("3Dレーザースキャナー 測量機器"),
        google_news_url("LiDAR ドローン 導入"),
        google_news_url("SLAM 測量 新技術"),
        google_news_url("ハンディSLAM"),
        news_url("Trimble 測量", "ja-JP"),
        news_url("ライカ ジオシステムズ", "ja-JP"),
        news_url("トプコン 測量", "ja-JP"),
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
    "🛠️ Surveying Equipment & LiDAR (New Products & Trends)": [
        google_news_url("Trimble surveying OR LiDAR new product", "en", "US", "US:en"),
        google_news_url("Leica Geosystems BLK surveying", "en", "US", "US:en"),
        google_news_url("CHCNAV mapping", "en", "US", "US:en"),
        google_news_url("Topcon positioning new release", "en", "US", "US:en"),
        google_news_url("YellowScan UAV LiDAR", "en", "US", "US:en"),
        google_news_url("RIEGL laser scanner mapping", "en", "US", "US:en"),
        google_news_url("SLAM 3D mapping equipment", "en", "US", "US:en"),
        google_news_url("surveying Handheld SLAM", "en", "US", "US:en"),
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
    now_ts = time.time()

    for category, urls in categories.items():
        category_news = []
        for url in urls:
            try:
                # 取得を試行
                feed = feedparser.parse(url)
                # 1つのキーワードにつき上位15件程度を見る
                for entry in feed.entries[:15]:
                    link = entry.get("link", "")
                    if link in seen_links:
                        continue
                    
                    title = entry.title
                    # タイトルが「No Image」等の不適切なものはスキップ
                    if not title or "no image" in title.lower():
                        continue

                    # 測量・LiDARなどのニッチな情報は絶対数が少ないため、期間フィルタを長め(60日)に設定して古い有益情報を取りこぼさない
                    entry_ts = get_timestamp(entry)
                    if entry_ts > 0 and (now_ts - entry_ts > 60 * 24 * 3600):
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
            
            # APIのレート制限（連続アクセスによるブロック）を回避するため1秒待機
            time.sleep(1)

        # 新しい順にソートして最大15件
        category_news.sort(key=lambda x: x["timestamp"], reverse=True)
        news_data[category] = category_news[:max_per_category]

    return news_data


def generate_html(domestic_data, international_data, international_translated, stock_data=None):
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
        stock_data=stock_data,
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Generated index.html at {update_time} JST.")


def fetch_stock_data():
    try:
        # First, try Google Finance which is often more strictly real-time and doesn't get stuck on old data
        print("Fetching real-time stock data from Google Finance...")
        import urllib.request
        import re
        url = "https://www.google.com/finance/quote/278A:TYO"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        price_match = re.search(r'class="YMlKec fxKbKc"[^>]*>([^<]+)', html)
        if price_match:
            price_str = price_match.group(1).replace('¥', '').replace('\\', '').replace(',', '').strip()
            price = float(price_str)
            
            # Fetch change string
            change_match = re.search(r'class="JwB6zf"[^>]*>([^<]+)', html)
            change_str = change_match.group(1).strip() if change_match else "0.00%"
            is_up = not change_str.startswith("-")

            # Google Finance gives absolute change right next to percentage usually, or we just supply percentage
            # Since change string is usually like '-0.40%' or '1.20%', we will try to parse it
            return {
                "price": f"{price:,.0f}",
                "change": change_str.split('分')[0] if '分' in change_str else "リアルタイム",  # fallback text if needed
                "change_percent": change_str,
                "is_up": is_up
            }
    except Exception as e:
        print(f"Google Finance failed: {e}. Trying yfinance fallback...")
        
    try:
        import yfinance as yf
        ticker = yf.Ticker("278A.T")
        # Use 1m interval to get real-time during market hours
        history = ticker.history(period="1mo", interval="1d") # fallback to daily if 1m is not available correctly for previous day comparison
        if memory_fallback := _yfinance_realtime(ticker):
             return memory_fallback
             
        if history is not None and not history.empty and len(history) >= 2:
            current_price = history['Close'].iloc[-1]
            prev_price = history['Close'].iloc[-2]
            change = current_price - prev_price
            change_percent = (change / prev_price) * 100
            return {
                "price": f"{current_price:,.0f}",
                "change": f"{abs(change):,.0f}",
                "change_percent": f"{abs(change_percent):.2f}%",
                "is_up": change >= 0
            }
    except Exception as e:
        print(f"yfinance failed: {e}")

    return None

def _yfinance_realtime(ticker):
    try:
        hist_1m = ticker.history(period="1d", interval="1m")
        hist_daily = ticker.history(period="5d", interval="1d")
        if not hist_1m.empty and len(hist_daily) >= 2:
            current_price = hist_1m['Close'].iloc[-1]
            prev_price = hist_daily['Close'].iloc[-2]
            change = current_price - prev_price
            change_percent = (change / prev_price) * 100
            return {
                "price": f"{current_price:,.0f}",
                "change": f"{abs(change):,.0f}",
                "change_percent": f"{abs(change_percent):.2f}%",
                "is_up": change >= 0
            }
    except:
        pass
    return None


if __name__ == "__main__":
    print("Fetching TerraDrone stock price...")
    stock_data = fetch_stock_data()

    print("Fetching domestic news...")
    domestic = fetch_category_data(DOMESTIC_CATEGORIES, max_per_category=20)

    print("Fetching international news...")
    # 海外ニュースの取得量を増加
    international = fetch_category_data(INTERNATIONAL_CATEGORIES, max_per_category=25)
    
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
    generate_html(domestic, international, international_translated, stock_data)
    print("Done!")
