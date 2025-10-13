from flask import Flask, jsonify, send_from_directory
import yfinance as yf
import time
import requests
from bs4 import BeautifulSoup
import feedparser
import re

app = Flask(__name__)

# --- Caching for Bangkok Bank Daily Report ---
last_bbl_result = None
last_bbl_time = 0

def get_google_technology_news():
    feed_url = "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZ4Y0dOc2JtVnpMVFF4T1NnQVAB?hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(feed_url)
        headlines = []
        for entry in feed.entries[:6]:
            title = entry.get('title', 'No title')
            link = entry.get('link', '')
            headlines.append(f"{title} ({link})")
        if not headlines:
            return "No recent Google Technology headlines found."
        return " | ".join(headlines)
    except Exception as e:
        return f"Error fetching Google Technology news: {e}"


def is_thai(text):
    # Returns True if the text contains any Thai character
    return bool(re.search(r'[\u0E00-\u0E7F]', text))

def get_cna_business_news():
    feed_url = "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6936"
    try:
        feed = feedparser.parse(feed_url)
        headlines = []
        for entry in feed.entries:
            title = entry.get('title', 'No title')
            link = entry.get('link', '')
            # Only include if there are NO Thai characters
            if not is_thai(title):
                headlines.append(f"{title} ({link})")
            if len(headlines) >= 6:
                break
        if not headlines:
            return "No recent CNA Business headlines found."
        return " | ".join(headlines)
    except Exception as e:
        return f"Error fetching CNA Business news: {e}"

def get_cna_business_news_thai():
    feed_url = "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6936"
    try:
        feed = feedparser.parse(feed_url)
        headlines = []
        for entry in feed.entries:
            title = entry.get('title', 'No title')
            link = entry.get('link', '')
            # Only include if there ARE Thai characters
            if is_thai(title):
                headlines.append(f"{title} ({link})")
            if len(headlines) >= 6:
                break
        if not headlines:
            return "No recent Thai business headlines found."
        return " | ".join(headlines)
    except Exception as e:
        return f"Error fetching Thai business news: {e}"

def get_bangkokpost_business_news():
    feed_url = "https://www.bangkokpost.com/rss/data/business.xml"
    try:
        feed = feedparser.parse(feed_url)
        headlines = []
        for entry in feed.entries[:6]:
            headlines.append(f"{entry.title} ({entry.link})")
        return " | ".join(headlines)
    except Exception as e:
        return f"Error fetching Bangkok Post Business news: {e}"

def get_thairath_news():
    feed_url = "https://www.thairath.co.th/rss/news"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(feed_url, headers=headers, timeout=10)
        feed = feedparser.parse(r.content)
        headlines = []
        for entry in feed.entries[:6]:
            title = entry.get('title', 'No title')
            link = entry.get('link', '')
            headlines.append(f"{title} ({link})")
        if not headlines:
            return "No recent Thairath headlines found."
        return " | ".join(headlines)
    except Exception as e:
        return f"Error fetching Thairath news: {e}"

def get_fxleaders_usdthb_forecast():
    url = "https://www.fxleaders.com/forecasts/forex/usd-thb-price-forecast/"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        main = soup.find("div", class_="entry-content")
        if main:
            p = main.find("p")
            if p:
                return p.text.strip()
        return "No FXLeaders forecast found."
    except Exception as e:
        return f"Error fetching FXLeaders forecast: {e}"

def get_bangkokbank_daily_report():
    global last_bbl_result, last_bbl_time
    if time.time() - last_bbl_time < 300 and last_bbl_result:
        return last_bbl_result

    url = "https://www.bangkokbank.com/en/Business-Banking/Market-Reports"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", class_="card-body")
            for card in cards:
                title = card.find("h5")
                if title and "Daily Report" in title.text:
                    link = card.find("a", href=True)
                    date = card.find("span", class_="date")
                    if link:
                        report_url = "https://www.bangkokbank.com" + link['href']
                        report_title = title.text.strip()
                        report_date = date.text.strip() if date else ""
                        result = f"{report_title} ({report_date}): {report_url}"
                        last_bbl_result = result
                        last_bbl_time = time.time()
                        return result
            result = "No Daily Report found."
            last_bbl_result = result
            last_bbl_time = time.time()
            return result
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                result = (
                    "Unable to fetch the latest Bangkok Bank Daily Report. "
                    "Please check the [Bangkok Bank Market Reports page]"
                    "(https://www.bangkokbank.com/en/Business-Banking/Market-Reports) directly."
                )
                last_bbl_result = result
                last_bbl_time = time.time()
                return result

@app.route('/api/analysis')
def get_analysis():
    analysis = {
        "Latest news": (
            "Bangkok Post: " + get_bangkokpost_business_news() +
            " | CNA Business: " + get_cna_business_news() +
            " | Local news in Thai: " + get_thairath_news()
        ),
        "technology_news": get_google_technology_news(),  # <-- fixed here
        "bangkok_bank": get_bangkokbank_daily_report(),
        "scb_eic": "See SCB EIC website for latest analysis.",
        "uob": "See UOB website for latest analysis.",
        "kresearch": "See Kasikorn Research for latest analysis."
    }
    return jsonify(analysis)

@app.route('/api/chartdata')
def get_chartdata():
    ticker = yf.Ticker("USDTHB=X")
    hist = ticker.history(period="2mo", interval="1d")
    daily = []
    for idx, row in hist.iterrows():
        daily.append({
            "date": idx.strftime("%Y-%m-%d"),
            "value": float(row['Close'])
        })

    hist_intra = ticker.history(period="1d", interval="15m")
    intraday = []
    for idx, row in hist_intra.iterrows():
        # idx is a pandas.Timestamp, localize to Asia/Bangkok and output ISO string
        if idx.tzinfo is None:
            idx = idx.tz_localize('UTC')
        ts = idx.tz_convert('Asia/Bangkok').isoformat()
        intraday.append({
            "timestamp": ts,
            "value": float(row['Close'])
        })

    return jsonify({"daily": daily, "intraday": intraday})


@app.route('/')
def serve_dashboard():
    return send_from_directory('.', 'FX_THB_fn.html')

@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081)
