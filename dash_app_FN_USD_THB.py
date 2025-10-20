import dash
from dash import dcc, html, Input, Output, State, callback
import plotly.graph_objs as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import requests
import feedparser
import re
import os
import fitz # PyMuPDF
import yfinance as yf
import sys # For setting up mock paths for the environment
from bs4 import BeautifulSoup # Import BeautifulSoup

# =============================
# CONFIGURATION & MOCK SETUP
# =============================

# Define a virtual directory for the application's file system structure.
# NOTE: In a real environment, you must ensure this directory exists and contains the sample PDFs.
DOWNLOAD_DIR = "/temp/FN_FX_Analysis"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# MOCK FILE PATHS: Since this code runs in a sandbox, these paths
# are mockups. The user must ensure these files are available in a real environment
# for the PDF analysis to succeed.
BANGKOK_BANK_SAMPLE = "market reports_Bangkok_bank_sample.pdf"
UOB_SAMPLE = "UOB_Market_Overview_sample.pdf"

# =============================
# PDF ANALYSIS SYSTEM
# =============================

class AutomatedPDFAnalyzer:
    """Handles automatic download (simulated) and text analysis of market reports."""
    def __init__(self):
        self.bangkok_tz = pytz.timezone('Asia/Bangkok')

    def get_expected_report_date(self):
        """Get expected report date (today on weekdays, last Friday on weekends)"""
        today = datetime.now(self.bangkok_tz)

        if today.weekday() >= 5:  # Weekend (Sat=5, Sun=6)
            # Calculate days back to the last Friday (4)
            days_to_friday = (today.weekday() - 4) % 7
            friday = today - timedelta(days=days_to_friday)
            return friday.strftime('%d %B %Y')
        else:
            return today.strftime('%d %B %Y')

    def auto_download_and_analyze(self):
        """Simulates download and analyzes the PDFs from the current working directory."""

        # --- Simulated Download/Local Access ---
        # In a real app, complex web automation (like Selenium) would replace this.

        try:
            results = {
                'bangkok_bank': self.analyze_bangkok_bank_pdf(BANGKOK_BANK_SAMPLE),
                'uob': self.analyze_uob_pdf(UOB_SAMPLE),
                'timestamp': datetime.now(self.bangkok_tz).isoformat(),
                'expected_date': self.get_expected_report_date()
            }

            return results

        except Exception as e:
            return {'error': f'Automation failed: {str(e)}'}

    def analyze_bangkok_bank_pdf(self, pdf_path):
        """Analyze Bangkok Bank PDF for FX Outlook content."""
        try:
            if not os.path.exists(pdf_path):
                # Return failure if sample file is not found (common in sandbox)
                return {'status': 'error', 'error': f'PDF file not found locally: {pdf_path}', 'debug_text': 'Missing required sample file.'}

            pdf_document = fitz.open(pdf_path)
            full_text = ""

            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                full_text += page.get_text() + "\n"

            pdf_document.close()

            extraction = self.extract_bangkok_bank_content(full_text)

            if extraction['success']:
                analysis = self.analyze_bangkok_bank_content(extraction['content'])
                return {
                    'status': 'success',
                    'report_date': extraction['date'],
                    'writer_name': extraction['writer_name'],
                    'content': extraction['content'],
                    'analysis': analysis,
                    'content_length': len(extraction['content']),
                    'source_file': os.path.basename(pdf_path)
                }
            else:
                return {'status': 'error', 'error': extraction['error'], 'debug_text': full_text[:1000]}

        except Exception as e:
            return {'status': 'error', 'error': f'PDF analysis error: {str(e)}'}

    def extract_bangkok_bank_content(self, full_text):
        """Extract date, writer, and FX Market Outlook content using regex."""
        try:
            # Find date
            date_pattern = r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})'
            date_match = re.search(date_pattern, full_text, re.IGNORECASE)

            if not date_match:
                return {'success': False, 'error': 'Could not find date in PDF'}

            report_date = date_match.group(1)

            # Find FX Market Outlook section
            fx_patterns = [
                r'FX Market Outlook\s*[-\—]?\s*written by\s*([^\n\r]+)(.*?)(?=THB Bonds Market Outlook|Bonds Market Outlook|Reference Rate|Deposit Rate|$)',
                r'FX Market Outlook(.*?)(?=THB Bonds Market Outlook|Bonds Market Outlook|$)',
                r'FX Market Outlook(.*)'
            ]

            writer_name = "Unknown"
            content = ""
            for pattern in fx_patterns:
                fx_match = re.search(pattern, full_text, re.DOTALL | re.IGNORECASE)
                if fx_match:
                    if 'written by' in pattern and fx_match.lastindex and fx_match.lastindex >= 1:
                        writer_name = fx_match.group(1).strip()
                        content = fx_match.group(2) if fx_match.lastindex >= 2 else fx_match.group(1)
                    else:
                        content = fx_match.group(1) if fx_match.lastindex else fx_match.group(0)

                    content = content.strip()
                    content = re.sub(r'\s+', ' ', content)  # Normalize whitespace

                    if len(content) > 50:
                        return {
                            'success': True,
                            'date': report_date,
                            'writer_name': writer_name,
                            'content': content
                        }

            return {'success': False, 'error': 'Could not extract FX Market Outlook content'}

        except Exception as e:
            return {'success': False, 'error': f'Extraction error: {str(e)}'}

    def analyze_bangkok_bank_content(self, content):
        """Analyze the extracted Bangkok Bank content for sentiment and rates."""
        analysis = {
            'summary': '',
            'key_points': [],
            'sentiment': 'neutral',
            'usd_thb_mentions': []
        }

        # Extract USD/THB rates (e.g., 32.154, 32.21/22)
        rate_patterns = [
            r'(\d+\.\d+)\s+THB/USD',
            r'(\d+\.\d+/\d+\.\d+)\s+THB/USD',
            r'(\d+\.\d+)/(\d+\.\d+)\s+THB/USD'
        ]

        rates = []
        for pattern in rate_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            rates.extend(matches)

        # Determine sentiment
        if 'depreciat' in content.lower() or 'weaker' in content.lower() or 'decline' in content.lower():
            analysis['sentiment'] = 'bearish (THB weakening)'
        elif 'appreciat' in content.lower() or 'stronger' in content.lower() or 'gain' in content.lower():
            analysis['sentiment'] = 'bullish (THB strengthening)'

        # Extract key points
        sentences = [s.strip() for s in re.split(r'[.!?]', content) if len(s.strip()) > 20]
        analysis['key_points'] = sentences[:5]

        # Generate summary
        summary_parts = []
        if rates:
            summary_parts.append(f"Rates mentioned: {len(rates)}")
        summary_parts.append(f"Sentiment: {analysis['sentiment']}")
        analysis['summary'] = "Bangkok Bank - " + " | ".join(summary_parts)

        return analysis

    def analyze_uob_pdf(self, pdf_path):
        """Analyze UOB PDF for FX content."""
        try:
            if not os.path.exists(pdf_path):
                # Return failure if sample file is not found (common in sandbox)
                return {'status': 'error', 'error': f'PDF file not found locally: {pdf_path}', 'debug_text': 'Missing required sample file.'}

            pdf_document = fitz.open(pdf_path)
            full_text = ""

            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                full_text += page.get_text() + "\n"

            pdf_document.close()

            # Extract FX section (often starts with 'FX' and ends before the next major section)
            fx_pattern = r'FX\s*(.*?)(?=Equities|Commodities|Bonds|Central Bank|Highlights Ahead|$)'
            fx_match = re.search(fx_pattern, full_text, re.DOTALL | re.IGNORECASE)

            if not fx_match:
                return {'status': 'error', 'error': 'FX section not found in UOB PDF', 'debug_text': full_text[:1000]}

            fx_content = fx_match.group(1).strip()
            fx_content = re.sub(r'\s+', ' ', fx_content)

            # Find date
            date_pattern = r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})'
            date_match = re.search(date_pattern, full_text, re.IGNORECASE)
            report_date = date_match.group(1) if date_match else "Unknown"

            if len(fx_content) < 50:
                return {'status': 'error', 'error': f'FX content too short: {len(fx_content)} characters', 'debug_text': fx_content}

            analysis = self.analyze_uob_content(fx_content)

            return {
                'status': 'success',
                'report_date': report_date,
                'content': fx_content,
                'analysis': analysis,
                'content_length': len(fx_content),
                'source_file': os.path.basename(pdf_path)
            }

        except Exception as e:
            return {'status': 'error', 'error': f'UOB analysis error: {str(e)}'}

    def analyze_uob_content(self, content):
        """Analyze UOB content for sentiment and key points."""
        analysis = {
            'summary': '',
            'key_points': [],
            'sentiment': 'neutral'
        }

        # Extract meaningful sentences
        sentences = [s.strip() for s in re.split(r'[.!?]', content) if len(s.strip()) > 20]
        analysis['key_points'] = sentences[:5]

        # Determine sentiment
        positive_words = ['appreciat', 'strengthen', 'bullish', 'positive', 'gain', 'strong']
        negative_words = ['depreciat', 'weaken', 'bearish', 'negative', 'loss', 'weak']

        pos_count = sum(1 for word in positive_words if word in content.lower())
        neg_count = sum(1 for word in negative_words if word in content.lower())

        if pos_count > neg_count * 1.5: # Slightly skewed to neutral unless strongly positive
            analysis['sentiment'] = 'bullish'
        elif neg_count > pos_count * 1.5:
            analysis['sentiment'] = 'bearish'

        analysis['summary'] = f"UOB - Sentiment: {analysis['sentiment']} | Key points: {len(analysis['key_points'])}"

        return analysis

# Initialize analyzer
pdf_analyzer = AutomatedPDFAnalyzer()

# =============================
# NEWS FEED FUNCTIONS
# =============================

def get_bangkokpost_business_news():
    """Get Bangkok Post business news"""
    try:
        feed_url = "https://www.bangkokpost.com/rss/data/business.xml"
        feed = feedparser.parse(feed_url)

        headlines = []
        for entry in feed.entries[:6]:
            title = entry.get('title', 'No title')
            link = entry.get('link', '#')
            headlines.append(f"{title} ({link})")

        return headlines if headlines else ["No recent Bangkok Post headlines found."]

    except Exception as e:
        return [f"Error fetching Bangkok Post news: {str(e)}"]

# Helper function to check for Thai characters (basic check)
def is_thai(text):
    return bool(re.search(r'[\u0E00-\u0E7F]', text))

def get_cna_business_news():
    """Get CNA business news using the provided URL and filtering."""
    feed_url = "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6936"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(feed_url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)
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
            return ["No recent CNA Business headlines found."]
        return headlines
    except Exception as e:
        return [f"Error fetching CNA Business news: {e}"]


def get_thairath_news():
    """Get Thairath news"""
    try:
        feed_url = "https://www.thairath.co.th/rss/news"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(feed_url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)

        headlines = []
        for entry in feed.entries[:6]:
            title = entry.get('title', 'No title')
            link = entry.get('link', '#')
            headlines.append(f"{title} ({link})")

        return headlines if headlines else ["No recent Thairath headlines found."]

    except Exception as e:
        return [f"Error fetching Thairath news: {str(e)}"]

# =============================
# DASH APP DEFINITION
# =============================

# Initialize Dash application
app = dash.Dash(__name__, title="Automated FX Analysis Dashboard")

# Inline CSS for aesthetics
EXTERNAL_STYLESHEET = [
    {
        'href': 'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap',
        'rel': 'stylesheet'
    },
    {
        'href': 'https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.min.css',
        'rel': 'stylesheet'
    }
]

app = dash.Dash(__name__, external_stylesheets=EXTERNAL_STYLESHEET)

# Define the application layout
app.layout = html.Div(style={'fontFamily': 'Inter, sans-serif', 'padding': '20px', 'maxWidth': '1200px', 'margin': '0 auto'}, children=[

    # Header
    html.Div([
        html.H1("💰 Automated FX Analysis Dashboard",
                style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '10px', 'fontWeight': 800}),
        html.P(f"Auto-downloads PDFs to {DOWNLOAD_DIR} (Simulated) and analyzes content",
               style={'textAlign': 'center', 'color': '#7f8c8d', 'marginBottom': '20px'}),
        html.Div([
            html.Span("🕒 ", style={'fontSize': '20px'}),
            html.Span(id="current-time", style={'fontSize': '18px', 'fontWeight': 'bold'}),
            html.Span(" Bangkok Time", style={'marginLeft': '8px', 'color': '#34495e'}),
            html.Span(" | Expected Report Date: ", style={'marginLeft': '25px', 'color': '#34495e'}),
            html.Span(id="expected-date", style={'fontWeight': 'bold', 'color': '#e67e22'})
        ], style={'textAlign': 'center'})
    ], style={'backgroundColor': '#ecf0f1', 'padding': '30px', 'borderRadius': '10px', 'marginBottom': '30px', 'boxShadow': '0 4px 8px rgba(0,0,0,0.1)'}),

    # Control Section
    html.Div([
        html.Button("🔄 Auto-Download & Analyze PDFs", id="analyze-pdfs-btn", n_clicks=0,
                    style={'backgroundColor': '#3498db', 'color': 'white', 'border': 'none',
                           'padding': '12px 24px', 'borderRadius': '8px', 'cursor': 'pointer', 'margin': '5px 10px',
                           'boxShadow': '0 2px 4px rgba(0,0,0,0.2)', 'transition': '0.3s'}),
        html.Button("📰 Update News Headlines", id="update-news-btn", n_clicks=0,
                    style={'backgroundColor': '#e67e22', 'color': 'white', 'border': 'none',
                           'padding': '12px 24px', 'borderRadius': '8px', 'cursor': 'pointer', 'margin': '5px 10px',
                           'boxShadow': '0 2px 4px rgba(0,0,0,0.2)', 'transition': '0.3s'}),
        html.Button("📈 Update Charts", id="update-charts-btn", n_clicks=0,
                    style={'backgroundColor': '#27ae60', 'color': 'white', 'border': 'none',
                           'padding': '12px 24px', 'borderRadius': '8px', 'cursor': 'pointer', 'margin': '5px 10px',
                           'boxShadow': '0 2px 4px rgba(0,0,0,0.2)', 'transition': '0.3s'})
    ], style={'textAlign': 'center', 'marginBottom': '30px'}),

    # Status Display
    html.Div(id="status-display", style={'marginBottom': '30px'}),

    # News Section
    html.Div([
        html.H2("📰 Latest News Headlines",
                style={'color': '#2c3e50', 'borderBottom': '3px solid #3498db', 'paddingBottom': '10px', 'marginBottom': '20px'}),

        html.Div([
            html.Div([
                html.H3("🇹🇭 Bangkok Post Business", style={'color': '#2980b9', 'fontSize': '1.5rem'}),
                html.Ul(id="bangkok-post-news", style={
                    'backgroundColor': 'white', 'padding': '15px', 'borderRadius': '8px',
                    'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'minHeight': '200px', 'listStyleType': 'disc'
                })
            ], className="four columns"),

            html.Div([
                html.H3("🇸🇬 CNA Business", style={'color': '#e67e22', 'fontSize': '1.5rem'}),
                html.Ul(id="cna-news", style={
                    'backgroundColor': 'white', 'padding': '15px', 'borderRadius': '8px',
                    'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'minHeight': '200px', 'listStyleType': 'disc'
                })
            ], className="four columns"),

            html.Div([
                html.H3("🇹🇭 Thairath News", style={'color': '#8e44ad', 'fontSize': '1.5rem'}),
                html.Ul(id="thairath-news", style={
                    'backgroundColor': 'white', 'padding': '15px', 'borderRadius': '8px',
                    'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'minHeight': '200px', 'listStyleType': 'disc'
                })
            ], className="four columns")
        ], className="row")
    ], style={'marginBottom': '40px'}),

    # PDF Analysis Section
    html.Div([
        html.H2("🏦 Automated PDF Analysis Summary",
                style={'color': '#2c3e50', 'borderBottom': '3px solid #3498db', 'paddingBottom': '10px', 'marginBottom': '20px'}),

        html.Div([
            html.Div([
                html.H3("🏦 Bangkok Bank FX Outlook", style={'color': '#2980b9', 'fontSize': '1.5rem'}),
                html.Div(id="bangkok-bank-analysis", style={
                    'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '8px',
                    'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'minHeight': '350px'
                })
            ], className="six columns"),

            html.Div([
                html.H3("🏦 UOB Markets Overview (FX)", style={'color': '#e67e22', 'fontSize': '1.5rem'}),
                html.Div(id="uob-analysis", style={
                    'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '8px',
                    'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'minHeight': '350px'
                })
            ], className="six columns")
        ], className="row")
    ], style={'marginBottom': '40px'}),

    # Charts Section
    html.Div([
        html.H2("📈 USD/THB Exchange Rate Charts (Data via Yahoo Finance)",
                style={'color': '#2c3e50', 'borderBottom': '3px solid #3498db', 'paddingBottom': '10px', 'marginBottom': '20px'}),

        html.Div([
            dcc.Graph(id="yearly-chart", style={'height': '400px', 'borderRadius': '8px', 'boxShadow': '0 4px 8px rgba(0,0,0,0.1)'})
        ], style={'marginBottom': '30px'}),

        html.Div([
            dcc.Graph(id="intraday-chart", style={'height': '400px', 'borderRadius': '8px', 'boxShadow': '0 4px 8px rgba(0,0,0,0.1)'})
        ])
    ]),

    # Auto-refresh intervals
    dcc.Interval(id='time-interval', interval=1000, n_intervals=0), # 1 second for clock
    dcc.Interval(id='data-interval', interval=300000, n_intervals=0), # 5 minutes for data/news/PDF
])

# =============================
# CALLBACKS
# =============================

@app.callback(
    [Output('current-time', 'children'),
     Output('expected-date', 'children')],
    Input('time-interval', 'n_intervals')
)
def update_time_and_date(n):
    """Updates the live clock and expected report date."""
    current_time = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')
    expected_date = pdf_analyzer.get_expected_report_date()
    return current_time, expected_date

@app.callback(
    [Output('bangkok-post-news', 'children'),
     Output('cna-news', 'children'),
     Output('thairath-news', 'children')],
    [Input('update-news-btn', 'n_clicks'),
     Input('data-interval', 'n_intervals')]
)
def update_news(n_clicks, n_intervals):
    """Fetches and displays news headlines on button click or interval."""

    # Get news from all sources
    bangkok_news = get_bangkokpost_business_news()
    cna_news = get_cna_business_news()
    thairath_news = get_thairath_news()

    # Format as list items
    def format_news_items(news_list):
        items = []
        for item in news_list:
            # Simple link extraction for display
            match = re.search(r'\((.*?)\)', item)
            title = item
            link = '#'
            if match:
                link = match.group(1)
                title = item.replace(match.group(0), "").strip()

            items.append(html.Li(
                html.A(title, href=link, target="_blank", style={'color': '#2c3e50', 'textDecoration': 'none', 'transition': '0.3s', 'display': 'block', 'padding': '5px 0'}),
                style={'borderBottom': '1px solid #f0f0f0', 'marginBottom': '5px', 'fontSize': '14px'}
            ))
        return items

    return format_news_items(bangkok_news), format_news_items(cna_news), format_news_items(thairath_news)

@app.callback(
    [Output('bangkok-bank-analysis', 'children'),
     Output('uob-analysis', 'children'),
     Output('status-display', 'children')],
    [Input('analyze-pdfs-btn', 'n_clicks'),
     Input('data-interval', 'n_intervals')]
)
def update_pdf_analysis(n_clicks, n_intervals):
    """Performs and displays PDF analysis results."""

    if n_clicks == 0 and n_intervals == 0:
        # Initial state before first interaction
        initial_msg = html.Div("Awaiting first analysis run. Please click 'Auto-Download & Analyze PDFs' or wait for the 5-minute auto-refresh.",
                               style={'color': '#7f8c8d', 'textAlign': 'center', 'padding': '50px'})
        status_msg = html.Div(f"Ready to analyze PDFs from {os.path.abspath(os.curdir)} when triggered.",
                              style={'color': '#3498db', 'textAlign': 'center', 'padding': '10px', 'backgroundColor': '#e8f4fd', 'borderRadius': '5px'})
        return initial_msg, initial_msg, status_msg

    try:
        # Auto-download and analyze PDFs (using mock paths)
        results = pdf_analyzer.auto_download_and_analyze()

        if 'error' in results:
            error_msg = html.Div(f"❌ Automation System Error: {results['error']}", style={'color': '#e74c3c', 'textAlign': 'center', 'padding': '10px', 'backgroundColor': '#fdeded', 'borderRadius': '5px'})
            return error_msg, error_msg, error_msg

        # Helper function for rendering analysis results
        def render_analysis(result, bank_name):
            if result['status'] == 'success':
                sentiment_color = '#27ae60' if 'bullish' in result['analysis']['sentiment'].lower() else '#e74c3c' if 'bearish' in result['analysis']['sentiment'].lower() else '#f39c12'

                return html.Div([
                    html.Div([
                        html.Span("✅ ", style={'color': '#27ae60', 'fontSize': '20px'}),
                        html.Span("Analysis Successful", style={'fontWeight': 'bold', 'color': '#2c3e50'})
                    ], style={'marginBottom': '10px'}),
                    html.P([html.Strong("Date: "), html.Span(result['report_date'])]),
                    html.P([html.Strong("Source File: "), html.Span(result['source_file'])]),
                    html.P([html.Strong("FX Sentiment: "), html.Span(result['analysis']['sentiment'].upper(), style={'color': sentiment_color, 'fontWeight': 'bold'})]),
                    html.P([html.Strong("Summary: "), html.Span(result['analysis']['summary'])]),
                    html.Hr(),
                    html.Strong("Key Points Preview:"),
                    html.Ul([html.Li(p, style={'fontSize': '14px', 'color': '#666'}) for p in result['analysis']['key_points']], style={'paddingLeft': '20px', 'marginTop': '10px'}),
                    html.Div(f"...Content Length: {result['content_length']} characters", style={'fontSize': '10px', 'color': '#999', 'marginTop': '15px'})
                ])
            else:
                return html.Div([
                    html.Div([
                        html.Span("❌ ", style={'color': '#e74c3c', 'fontSize': '20px'}),
                        html.Span(f"{bank_name} Analysis Failed", style={'fontWeight': 'bold', 'color': '#e74c3c'})
                    ]),
                    html.P(f"Error: {result['error']}"),
                    html.P("HINT: Ensure the required PDF sample file is accessible at the expected path.", style={'fontSize': '12px', 'color': '#888'}),
                    html.Details([
                        html.Summary("Show Debug Info"),
                        html.Div(result.get('debug_text', 'No debug info available.'), style={'fontSize': '10px', 'color': '#999', 'fontFamily': 'monospace', 'whiteSpace': 'pre-wrap'})
                    ])
                ])

        bb_display = render_analysis(results['bangkok_bank'], "Bangkok Bank")
        uob_display = render_analysis(results['uob'], "UOB")

        # Status Display
        status_display = html.Div([
            html.P("✅ PDF Analysis Completed Successfully", style={'color': '#27ae60', 'fontWeight': 'bold'}),
            html.P(f"🕒 Last Analysis Run: {datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')} BKK Time"),
            html.P(f"🎯 Reports Expected For: {results['expected_date']}"),
            html.P(f"📁 Files Analyzed (Simulated): {BANGKOK_BANK_SAMPLE}, {UOB_SAMPLE}")
        ], style={'backgroundColor': '#f8f9fa', 'padding': '15px', 'borderRadius': '5px', 'border': '1px solid #dcdcdc'})

        return bb_display, uob_display, status_display

    except Exception as e:
        error_display = html.Div(f"❌ Critical Callback Error: {str(e)}", style={'color': '#e74c3c', 'padding': '10px', 'backgroundColor': '#fdeded', 'borderRadius': '5px'})
        return error_display, error_display, error_display

@app.callback(
    [Output('yearly-chart', 'figure'),
     Output('intraday-chart', 'figure')],
    [Input('update-charts-btn', 'n_clicks'),
     Input('data-interval', 'n_intervals')]
)
def update_charts(n_clicks, n_intervals):
    """Fetches USD/THB data and generates Plotly charts."""

    # Define a robust way to get data, falling back to dummy data on failure
    try:
        ticker = yf.Ticker("USDTHB=X")

        # 12-month chart (Daily data)
        # Fetching 2 years to ensure enough data for 12mo period even if there are gaps
        print("Attempting to fetch yearly data...")
        hist_yearly = ticker.history(period="2y", interval="1d")
        hist_yearly = hist_yearly.last('12mo') # Select the last 12 months
        print(f"Yearly data fetched: {hist_yearly.shape[0]} rows")

        if hist_yearly.empty:
            raise ValueError("Yahoo Finance returned empty data for 12mo history.")

        yearly_fig = go.Figure()
        yearly_fig.add_trace(go.Scatter(
            x=hist_yearly.index,
            y=hist_yearly['Close'],
            mode='lines',
            name='USD/THB Close',
            line=dict(color='#3498db', width=2)
        ))
        yearly_fig.update_layout(
            title={'text': 'USD/THB Exchange Rate - 12 Month Trend', 'x': 0.5},
            xaxis_title='Date',
            yaxis_title='THB per USD',
            template='plotly_white',
            margin=dict(l=40, r=40, t=60, b=40),
            hovermode="x unified"
        )

        # 15-minute intraday chart
        # Request 5 days of data at 15m interval to ensure some data is always returned
        print("Attempting to fetch intraday data...")
        hist_intraday = ticker.history(period="5d", interval="15m")
        print(f"Intraday data fetched: {hist_intraday.shape[0]} rows")

        # Filter only for today's data (Bangkok Time)
        bkk_tz = pytz.timezone('Asia/Bangkok')
        today_date = datetime.now(bkk_tz).date()

        # Convert index to BKK timezone before comparing date
        hist_intraday_today = hist_intraday[hist_intraday.index.tz_convert(bkk_tz).date == today_date]

        print(f"Intraday data for today: {hist_intraday_today.shape[0]} rows")


        if hist_intraday_today.empty:
            raise ValueError("Yahoo Finance returned empty data for today's intraday.")

        intraday_fig = go.Figure()
        intraday_fig.add_trace(go.Scatter(
            x=hist_intraday_today.index,
            y=hist_intraday_today['Close'],
            mode='lines+markers',
            name='USD/THB Close',
            line=dict(color='#e74c3c', width=1),
            marker=dict(size=4)
        ))
        intraday_fig.update_layout(
            title={'text': 'USD/THB Exchange Rate - 15 Minute Intervals (Today)', 'x': 0.5},
            xaxis_title='Time (UTC, or conversion)',
            yaxis_title='THB per USD',
            template='plotly_white',
            margin=dict(l=40, r=40, t=60, b=40),
            hovermode="x unified"
        )

        return yearly_fig, intraday_fig

    except Exception as e:
        # Fallback sample data and log error
        print(f"Chart Error (Falling back to dummy data): {str(e)}", file=sys.stderr)

        # Yearly Sample
        dates_yearly = pd.date_range(end=datetime.now(), periods=365, freq='D')
        np.random.seed(0)
        data_yearly = 33 + np.random.randn(365).cumsum() * 0.05
        sample_fig_yearly = go.Figure()
        sample_fig_yearly.add_trace(go.Scatter(x=dates_yearly, y=data_yearly, mode='lines', name='Sample USD/THB'))
        sample_fig_yearly.update_layout(
            title={'text': 'USD/THB - 12 Month Trend (DUMMY DATA - Live Data Fetch Failed)', 'x': 0.5, 'font': {'color': 'red'}},
            xaxis_title='Date',
            yaxis_title='THB per USD'
        )

        # Intraday Sample
        dates_intraday = pd.date_range(end=datetime.now(), periods=96, freq='15min')
        data_intraday = data_yearly[-1] + np.random.randn(96).cumsum() * 0.005
        sample_fig_intraday = go.Figure()
        sample_fig_intraday.add_trace(go.Scatter(x=dates_intraday, y=data_intraday, mode='lines+markers', name='Sample USD/THB'))
        sample_fig_intraday.update_layout(
            title={'text': 'USD/THB - 15 Minute Intervals (DUMMY DATA - Live Data Fetch Failed)', 'x': 0.5, 'font': {'color': 'red'}},
            xaxis_title='Time',
            yaxis_title='THB per USD'
        )

        return sample_fig_yearly, sample_fig_intraday

if __name__ == '__main__':
    # Standard Dash run command
    app.run(debug=True)

print("\nDash application is running. Look for a public URL or port forwarding information.")
print(f"Expected download directory: {DOWNLOAD_DIR}")