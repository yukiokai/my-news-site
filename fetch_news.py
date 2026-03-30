def format_date(date_str):
    try:
        if date_str:
            if len(date_str) > 25:
                return date_str[:22]
            return date_str
    except Exception:
        pass
    return date_str

import urllib.request
import json
import xml.etree.ElementTree as ET
import time
from datetime import datetime
import os
import pytz

try:
    import feedparser
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("Dependencies not met. Please run: pip install -r requirements.txt")
    exit(1)

FEEDS = {
    "📰 国内ニュース": [
        {"url": "https://news.yahoo.co.jp/rss/topics/domestic.xml", "source": "Yahoo!国内"},
        {"url": "https://www.nhk.or.jp/rss/news/cat1.xml", "source": "NHK社会"}
    ],
    "🌍 国際ニュース": [
        {"url": "https://news.yahoo.co.jp/rss/topics/world.xml", "source": "Yahoo!国際"},
        {"url": "https://www.nhk.or.jp/rss/news/cat6.xml", "source": "NHK国際"}
    ],
    "💻 テクノロジー・IT": [
        {"url": "https://news.yahoo.co.jp/rss/topics/it.xml", "source": "Yahoo! IT"},
        {"url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml", "source": "ITmedia"}
    ],
    "📈 経済・ビジネス": [
        {"url": "https://news.yahoo.co.jp/rss/topics/business.xml", "source": "Yahoo!経済"},
        {"url": "https://www.nhk.or.jp/rss/news/cat5.xml", "source": "NHK経済"}
    ]
}

def fetch_feed_data():
    news_data = {}
    for category, sources in FEEDS.items():
        category_news = []
        for source in sources:
            try:
                feed = feedparser.parse(source["url"])
                for entry in feed.entries[:8]:
                    pub_date = entry.get("published", entry.get("updated", ""))
                    published_parsed = entry.get("published_parsed", entry.get("updated_parsed"))
                    timestamp = time.mktime(published_parsed) if published_parsed else 0

                    category_news.append({
                        "title": entry.title,
                        "link": entry.link,
                        "source": source["source"],
                        "date": format_date(pub_date),
                        "timestamp": timestamp
                    })
            except Exception as e:
                print(f"Error fetching {source['url']}: {e}")
        
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
