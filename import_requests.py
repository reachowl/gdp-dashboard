import requests
import fitz  # PyMuPDF
import re
import os
import json
from datetime import datetime, timedelta
import pytz
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import time

# =============================
# CONFIGURATION
# =============================

DOWNLOAD_DIR = "./temp/FN_FX_Analysis"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =============================
# PDF DOWNLOAD & ANALYSIS
# =============================

class FXPDFAnalyzer:
    def __init__(self):
        self.bangkok_tz = pytz.timezone('Asia/Bangkok')
    
    def get_target_date(self):
        """Get target date for PDF download (today on weekdays, last Friday on weekends)"""
        today = datetime.now(self.bangkok_tz)
        
        if today.weekday() >= 5:  # Weekend (Sat=5, Sun=6)
            days_to_friday = (today.weekday() - 4) % 7
            target_date = today - timedelta(days=days_to_friday)
        else:
            target_date = today
            
        return target_date
    
    def download_uob_pdf(self):
        """Download UOB PDF using direct URL pattern"""
        target_date = self.get_target_date()
        filename = f"MO_{target_date.strftime('%y%m%d')}.pdf"
        base_url = "https://www.uobgroup.com/assets/web-resources/research/pdf/"
        pdf_url = urljoin(base_url, filename)
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(pdf_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                file_path = os.path.join(DOWNLOAD_DIR, filename)
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"✅ UOB PDF downloaded: {filename}")
                return file_path
            else:
                print(f"❌ UOB PDF not found: {filename} (HTTP {response.status_code})")
                return None
        except Exception as e:
            print(f"❌ Error downloading UOB PDF: {str(e)}")
            return None
    
    def scrape_bangkok_bank_reports(self):
        """Scrape Bangkok Bank market reports directly from their website with detailed investigation"""
        try:
            url = "https://www.bangkokbank.com/en/Business-Banking/Market-Reports"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            print(f"🌐 Scraping Bangkok Bank market reports from: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                return {'error': f'HTTP {response.status_code} - Failed to fetch page'}
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Debug: Save the HTML for inspection
            with open(os.path.join(DOWNLOAD_DIR, 'bangkok_bank_page.html'), 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            print("💾 Saved page HTML for inspection")
            
            # Let's investigate the page structure
            print("\n🔍 Investigating page structure...")
            
            # Check for common market report patterns
            print("📊 Looking for market report content...")
            
            # 1. Look for article tags
            articles = soup.find_all('article')
            print(f"   Found {len(articles)} article tags")
            
            # 2. Look for content containers
            content_selectors = [
                '.content', '.main-content', '.page-content', 
                '.article-content', '.news-content', '.report-content',
                '.body-copy', '.text-content', '[class*="content"]',
                '[class*="article"]', '[class*="news"]', '[class*="report"]'
            ]
            
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"   Found {len(elements)} elements with selector: {selector}")
            
            # 3. Look for specific market report sections
            market_keywords = ['market', 'report', 'fx', 'currency', 'outlook', 'analysis']
            for keyword in market_keywords:
                elements = soup.find_all(string=re.compile(keyword, re.IGNORECASE))
                if elements:
                    print(f"   Found {len(elements)} elements containing '{keyword}'")
            
            # 4. Look for PDF links or downloadable content
            pdf_links = soup.find_all('a', href=re.compile(r'\.pdf', re.IGNORECASE))
            print(f"   Found {len(pdf_links)} PDF links")
            for link in pdf_links[:3]:  # Show first 3 PDF links
                href = link.get('href', '')
                text = link.get_text(strip=True)
                print(f"     PDF: {text} -> {href}")
            
            # 5. Extract main content areas
            main_content = ""
            
            # Try to find the main content container
            main_selectors = [
                'main', 'article', '.main-content', '.content-area',
                '#main', '#content', '.page-content'
            ]
            
            for selector in main_selectors:
                element = soup.select_one(selector)
                if element:
                    main_content = element.get_text(strip=True)
                    print(f"✅ Found main content with selector: {selector}")
                    break
            
            # If no main content found, use body
            if not main_content:
                main_content = soup.find('body').get_text(strip=True)
                print("⚠️ Using body content as fallback")
            
            # Clean up the content
            main_content = re.sub(r'\s+', ' ', main_content)
            
            # Look for specific FX Market Outlook patterns
            print("\n🔍 Searching for FX Market Outlook content...")
            
            fx_patterns = [
                r'FX Market Outlook.*?written by.*?(.*?)(?=THB Bonds Market Outlook|Bonds Market Outlook|Market Outlook|$)',
                r'FX Market Outlook(.*?)(?=THB Bonds Market Outlook|$)',
                r'USD/THB.*?(?=THB Bonds Market Outlook|$)',
                r'Foreign Exchange.*?Outlook(.*?)(?=Bonds|Equities|Commodities|$)',
            ]
            
            fx_content = None
            for i, pattern in enumerate(fx_patterns):
                match = re.search(pattern, main_content, re.DOTALL | re.IGNORECASE)
                if match:
                    if match.lastindex:
                        fx_content = match.group(1).strip()
                    else:
                        fx_content = match.group(0).strip()
                    print(f"✅ Found FX content with pattern {i+1}")
                    break
            
            # Extract date from the page
            date_patterns = [
                r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
                r'(\d{1,2}/\d{1,2}/\d{4})',
                r'(\d{4}-\d{2}-\d{2})',
                r'Date:\s*(\d{1,2}\s+\w+\s+\d{4})',
                r'Report Date:\s*(\d{1,2}\s+\w+\s+\d{4})',
            ]
            
            report_date = None
            for pattern in date_patterns:
                date_match = re.search(pattern, main_content, re.IGNORECASE)
                if date_match:
                    report_date = date_match.group(1)
                    print(f"✅ Found date: {report_date}")
                    break
            
            if not report_date:
                report_date = self.get_target_date().strftime('%d %B %Y')
                print("⚠️ Using default date")
            
            # Prepare results
            if fx_content and len(fx_content) > 30:
                return {
                    'success': True,
                    'date': report_date,
                    'content': fx_content,
                    'content_length': len(fx_content),
                    'source': 'Bangkok Bank Website - FX Section',
                    'full_content_length': len(main_content)
                }
            elif len(main_content) > 200:
                # Return the most relevant part of main content
                relevant_content = main_content
                if len(relevant_content) > 1000:
                    relevant_content = relevant_content[:1000] + "..."
                
                return {
                    'success': True,
                    'date': report_date,
                    'content': relevant_content,
                    'content_length': len(relevant_content),
                    'source': 'Bangkok Bank Website - Main Content',
                    'full_content_length': len(main_content)
                }
            else:
                return {'error': 'No substantial market report content found on the page'}
                
        except Exception as e:
            return {'error': f'Scraping error: {str(e)}'}
    
    def analyze_bangkok_bank_content(self, scraped_data):
        """Analyze the scraped Bangkok Bank content"""
        if 'success' not in scraped_data:
            return scraped_data
        
        content = scraped_data['content']
        
        # Extract key information
        analysis = {
            'summary': '',
            'usd_thb_mentions': [],
            'sentiment': 'neutral',
            'key_points': []
        }
        
        # Find USD/THB rates
        rate_patterns = [
            r'USD/THB.*?(\d+\.\d+)',
            r'(\d+\.\d+)\s*THB',
            r'(\d+\.\d+)\s*/\s*(\d+\.\d+)',
            r'at\s*(\d+\.\d+)',
        ]
        
        for pattern in rate_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    analysis['usd_thb_mentions'].extend([m for m in match if 30.0 <= float(m) <= 40.0])
                else:
                    if 30.0 <= float(match) <= 40.0:
                        analysis['usd_thb_mentions'].append(match)
        
        # Determine sentiment
        content_lower = content.lower()
        positive_words = ['appreciat', 'strengthen', 'stronger', 'gain', 'bullish', 'positive', 'up', 'rise']
        negative_words = ['depreciat', 'weaken', 'weaker', 'decline', 'bearish', 'negative', 'down', 'fall']
        
        pos_count = sum(1 for word in positive_words if word in content_lower)
        neg_count = sum(1 for word in negative_words if word in content_lower)
        
        if pos_count > neg_count:
            analysis['sentiment'] = 'bullish (THB strengthening)'
        elif neg_count > pos_count:
            analysis['sentiment'] = 'bearish (THB weakening)'
        
        # Extract key sentences
        sentences = [s.strip() for s in re.split(r'[.!?]', content) if len(s.strip()) > 20]
        analysis['key_points'] = sentences[:4]
        
        # Create summary
        summary_parts = []
        if analysis['usd_thb_mentions']:
            unique_rates = list(set(analysis['usd_thb_mentions']))[:3]
            summary_parts.append(f"USD/THB: {', '.join(unique_rates)}")
        summary_parts.append(f"Sentiment: {analysis['sentiment']}")
        summary_parts.append(f"Key points: {len(analysis['key_points'])}")
        analysis['summary'] = " | ".join(summary_parts)
        
        return analysis
    
    def analyze_uob_pdf(self, pdf_path):
        """Analyze UOB PDF - extract FX section with multiple pattern attempts"""
        try:
            if not pdf_path or not os.path.exists(pdf_path):
                return {'error': 'PDF file not found'}
            
            pdf_document = fitz.open(pdf_path)
            full_text = ""
            
            # Extract text from all pages for better pattern matching
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                full_text += page.get_text() + "\n"
            
            pdf_document.close()
            
            # Debug: Save extracted text for inspection
            with open(os.path.join(DOWNLOAD_DIR, 'uob_extracted_text.txt'), 'w', encoding='utf-8') as f:
                f.write(full_text)
            print("💾 Saved UOB extracted text for inspection")
            
            # Multiple pattern attempts for UOB FX section
            patterns = [
                # Pattern 1: Between Central Bank Outlook and Equities
                r'Central Bank Outlook.*?FX\s*[▪•\-]\s*(.*?)(?=Equities|Commodities|Bonds|$)',
                # Pattern 2: Direct FX section with bullet
                r'FX\s*[▪•\-]\s*(.*?)(?=Equities|Commodities|Bonds|$)',
                # Pattern 3: Any FX content
                r'FX\s*(.*?)(?=Equities|Commodities|Bonds|$)',
                # Pattern 4: USD/THB specific content
                r'(USD/THB.*?)(?=Equities|Commodities|Bonds|$)',
            ]
            
            fx_content = None
            for pattern in patterns:
                match = re.search(pattern, full_text, re.DOTALL | re.IGNORECASE)
                if match:
                    fx_content = match.group(1).strip()
                    fx_content = re.sub(r'\s+', ' ', fx_content)  # Normalize whitespace
                    print(f"✅ Found UOB FX content with pattern {patterns.index(pattern) + 1}")
                    break
            
            if not fx_content:
                return {'error': 'FX section not found in UOB PDF'}
            
            # Find date
            date_patterns = [
                r'(\d{1,2}\s+\w+\s+\d{4})',  # 26 September 2025
                r'(\d{1,2}/\d{1,2}/\d{4})',   # 26/09/2025
                r'Markets Overview\s*\w+,\s*(\d{1,2}\s+\w+\s+\d{4})',  # Markets Overview Thursday, 25 September 2025
            ]
            
            date = "Unknown"
            for date_pattern in date_patterns:
                date_match = re.search(date_pattern, full_text, re.IGNORECASE)
                if date_match:
                    date = date_match.group(1)
                    break
            
            return {
                'success': True,
                'date': date,
                'content': fx_content,
                'content_length': len(fx_content)
            }
                
        except Exception as e:
            return {'error': f'Analysis error: {str(e)}'}
    
    def run_analysis(self):
        """Main function to download and analyze both sources"""
        print("🔄 Starting analysis...")
        target_date = self.get_target_date()
        print(f"📅 Target date: {target_date.strftime('%d %B %Y')}")
        
        # Get UOB PDF and Bangkok Bank web content
        print("\n📥 Downloading UOB PDF...")
        uob_pdf = self.download_uob_pdf()
        
        print("\n🌐 Scraping Bangkok Bank reports...")
        bbl_data = self.scrape_bangkok_bank_reports()
        
        # Analyze UOB PDF
        print("\n🔍 Analyzing UOB PDF...")
        uob_analysis = self.analyze_uob_pdf(uob_pdf) if uob_pdf else {'error': 'Failed to download UOB PDF'}
        
        # Analyze Bangkok Bank content
        print("🔍 Analyzing Bangkok Bank content...")
        if 'success' in bbl_data:
            bbl_analysis = self.analyze_bangkok_bank_content(bbl_data)
            bbl_analysis.update(bbl_data)  # Keep original data
        else:
            bbl_analysis = bbl_data
        
        results = {
            'target_date': target_date.strftime('%d %B %Y'),
            'uob': uob_analysis,
            'bangkok_bank': bbl_analysis
        }
        
        return results

# =============================
# USAGE EXAMPLE
# =============================

if __name__ == "__main__":
    analyzer = FXPDFAnalyzer()
    
    # Run analysis
    results = analyzer.run_analysis()
    
    print("\n" + "="*60)
    print("ANALYSIS RESULTS")
    print("="*60)
    
    print(f"\n🎯 Target Date: {results['target_date']}")
    
    print(f"\n🏦 BANGKOK BANK ANALYSIS:")
    print("-" * 40)
    if 'success' in results['bangkok_bank']:
        analysis = results['bangkok_bank']
        print(f"✅ Status: Success")
        print(f"✅ Date: {analysis['date']}")
        print(f"✅ Source: {analysis.get('source', 'Unknown')}")
        print(f"✅ Content length: {analysis['content_length']} chars")
        if 'full_content_length' in analysis:
            print(f"✅ Full page length: {analysis['full_content_length']} chars")
        if 'summary' in analysis:
            print(f"✅ Summary: {analysis['summary']}")
        if analysis['usd_thb_mentions']:
            print(f"✅ USD/THB rates found: {list(set(analysis['usd_thb_mentions']))}")
        print(f"✅ Sentiment: {analysis['sentiment']}")
        print(f"📝 Content Preview: {analysis['content'][:300]}...")
    else:
        print(f"❌ Error: {results['bangkok_bank']['error']}")
    
    print(f"\n🏦 UOB ANALYSIS:")
    print("-" * 40)
    if 'success' in results['uob']:
        analysis = results['uob']
        print(f"✅ Status: Success")
        print(f"✅ Date: {analysis['date']}")
        print(f"✅ Content length: {analysis['content_length']} chars")
        print(f"📝 Content Preview: {analysis['content'][:300]}...")
    else:
        print(f"❌ Error: {results['uob']['error']}")
    
    print(f"\n💾 Debug files saved in: {DOWNLOAD_DIR}")