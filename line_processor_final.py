# This Flask application handles LINE webhook events, performs OCR using the Gemini API,
# saves structured payment data to Firestore, and runs scheduled/on-demand email reports.

import flask
import os
import re
import requests
import json
import time
import base64
from datetime import datetime, timedelta
from threading import Thread
from io import StringIO
import csv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# --- 1. FIREBASE ADMIN & MOCK SETUP ---
# In a production environment, this will securely initialize Firebase Admin SDK.
try:
    from firebase_admin import initialize_app, firestore, credentials
    # Read the JSON credentials from the environment variable
    firebase_credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if firebase_credentials_json:
        # Load credentials from the string
        cred = credentials.Certificate(json.loads(firebase_credentials_json))
        initialize_app(cred)
        DB = firestore.client()
        print("Firebase Admin Initialized successfully.")
    else:
        raise ValueError("FIREBASE_CREDENTIALS_JSON environment variable not set.")
except Exception as e:
    print(f"Warning: Failed to initialize Firebase Admin SDK: {e}. Falling back to Mock.")
    
    # --- Firestore Mock for Local/Unconfigured Testing ---
    class FirestoreMock:
        def __init__(self):
            self.db = {} # {collection_path: {doc_id: data}}
            self.last_report_time = datetime.now() - timedelta(days=1)
            print("--- USING FIRESTORE MOCK ---")

        def collection(self, path):
            if path not in self.db:
                self.db[path] = {}
            return self

        def document(self, doc_id):
            return self

        def set(self, data):
            # In a mock, we don't need doc_id, just track the data
            doc_id = str(len(self.db['payments']))
            self.db['payments'][doc_id] = data
            print(f"Mock Save to payments/{doc_id}: {data['unit_id']} ({data['status']})")

        def get(self):
            # Used for retrieving the last report time setting
            return type('', (object,), {'to_dict': lambda: {'last_report_time': self.last_report_time}})()

        def update(self, data):
            # Used for updating the last report time
            self.last_report_time = data['last_report_time']
            print(f"Mock Update: last_report_time set to {self.last_report_time}")
            
        def where(self, field, op, value):
            return self

        def order_by(self, field):
            return self
        
        def limit(self, count):
            return self

        def stream(self):
            # Mock payments for testing reports
            mock_payments = [
                {'unit_id': '88/01', 'fee_month': '2025-10', 'amount': 1500.00, 'transaction_id': 'TIDMOCK1', 'email': 'a@a.com', 'timestamp': datetime.now() - timedelta(hours=3), 'status': 'COMPLETED', 'payer_name': 'Mock A'},
                {'unit_id': '88/02', 'fee_month': '2025-10', 'amount': 2500.00, 'transaction_id': 'TIDMOCK2', 'email': 'b@b.com', 'timestamp': datetime.now() - timedelta(hours=12), 'status': 'COMPLETED', 'payer_name': 'Mock B'},
            ]
            # Filter payments based on last report time (mocked filter)
            return [type('', (object,), {'to_dict': lambda: p})() for p in mock_payments if p['timestamp'] > self.last_report_time]
    
    DB = FirestoreMock()
    # Define collection paths based on assumed structure (private data for admin)
    APP_ID = os.getenv('RENDER_SERVICE_ID', 'default-app-id') # Use a Render ID or default
    PAYMENTS_COLLECTION = f'artifacts/{APP_ID}/users/admin_user/payments'
    SETTINGS_DOC = f'artifacts/{APP_ID}/users/admin_user/settings/report'


# --- 2. LINE API SETUP ---
# Load environment variables for LINE
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

# Conditional import for line-bot-sdk (requires pip install)
try:
    from linebot import LineBotApi, WebhookHandler
    from linebot.exceptions import InvalidSignatureError
    from linebot.models import MessageEvent, TextMessage, ImageMessage, StickerMessage, AudioMessage, ReplyMessage
    LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    HANDLER = WebhookHandler(LINE_CHANNEL_SECRET)
except ImportError:
    print("Warning: line-bot-sdk not installed. LINE functionality will not work.")
    LINE_BOT_API = None
    HANDLER = None

# --- 3. GEMINI API SETUP ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={GEMINI_API_KEY}"

# --- 4. EMAIL SETUP ---
ADMIN_REPORT_EMAIL = os.getenv("ADMIN_REPORT_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = "smtp.gmail.com" # Default to Gmail for common usage
SMTP_PORT = 587


class ProductionLineOAProcessor:
    def __init__(self, db_client):
        self.db = db_client
        self.valid_units = self._generate_valid_units()
        self.patterns = self._get_regex_patterns()
        self.last_report_time = self._get_last_report_time()
        print(f"Initialized with {len(self.valid_units)} valid units (88/01 to 88/165).")
        print(f"Last reported payment time: {self.last_report_time}")

    def _generate_valid_units(self):
        """Generates a set of valid unit IDs from 88/01 to 88/165."""
        units = set()
        for i in range(1, 166):
            units.add(f"88/{i:02d}")
        return units

    def _get_regex_patterns(self):
        """Defines comprehensive regex patterns for extracting required data."""
        return {
            # Extracts '88/##' with numbers 01 to 165
            'unit_id': r'88\/(0[1-9]|[1-9][0-9]|1[0-5][0-9]|16[0-5])',
            # Extracts YYYY-MM or YYYY/MM or YYYY.MM
            'fee_month': r'(\d{4}[-\/.]\d{1,2})',
            # Extracts common email format
            'email': r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            
            # --- OCR Extraction Patterns ---
            # Finds numbers (with commas/decimals) near monetary words (Baht/฿/Amount/Total/ยอด/รวม)
            'amount': r'([,\d]+\.?\d*)\s*(?:baht|บาท|total|amount|฿|ยอด|รวม|จำนวนเงิน)',
            # Finds Transaction ID (TID) or Reference (Ref) followed by alphanumeric string
            'transaction_id': r'(?:txn\s*id|transaction\s*id|ref\.?\s*no|เลขที่อ้างอิง|เลขที่รายการ):?\s*([A-Z0-9\-\s]+)',
            # Finds Payer Name near common labels (Sender/From/ผู้โอน/ชื่อ)
            'payer_name': r'(?:sender|from|ผู้โอน|ชื่อ):\s*([ก-๙a-zA-Z\s\.]+)',
        }

    def _get_last_report_time(self):
        """Retrieves the last successful report time from Firestore or defaults to 24 hours ago."""
        try:
            doc_ref = self.db.collection('settings').document('report')
            doc = doc_ref.get()
            if doc.to_dict() and 'last_report_time' in doc.to_dict():
                return doc.to_dict()['last_report_time']
            # Default to 24 hours ago if setting is missing
            return datetime.now() - timedelta(days=1)
        except Exception as e:
            print(f"Error fetching last report time: {e}. Defaulting to 24 hours ago.")
            return datetime.now() - timedelta(days=1)
    
    def _update_last_report_time(self, new_time):
        """Updates the last successful report time in Firestore."""
        try:
            doc_ref = self.db.collection('settings').document('report')
            doc_ref.set({'last_report_time': new_time}, merge=True)
            self.last_report_time = new_time
            print(f"Updated last_report_time to: {new_time}")
        except Exception as e:
            print(f"Error updating last report time: {e}")

    def _match_pattern(self, text, pattern_key):
        """Helper to find and clean a regex match."""
        pattern = self.patterns.get(pattern_key)
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            if pattern_key in ['amount']:
                # For amount, return the first group (the number) and clean it
                value = match.group(1).replace(',', '').strip()
                try:
                    return float(value)
                except ValueError:
                    return None
            elif pattern_key == 'payer_name':
                # Return the second group (the name) and strip
                return match.group(1).strip() if len(match.groups()) > 1 else match.group(0).strip()
            else:
                # For Unit ID, Month, TID, return the first group
                return match.group(1).strip()
        return None

    def _extract_receipt_data(self, ocr_text):
        """Extracts financial data from OCR text."""
        # Clean text for easier regex matching (remove extra newlines/spaces)
        text_clean = ocr_text.replace('\n', ' ').strip()
        
        data = {
            'amount': self._match_pattern(text_clean, 'amount'),
            'transaction_id': self._match_pattern(text_clean, 'transaction_id'),
            'payer_name': self._match_pattern(text_clean, 'payer_name'),
        }

        # Success requires both Amount and TID to be found
        data['success'] = data['amount'] is not None and data['transaction_id'] is not None
        return data

    def _image_to_text(self, image_bytes, image_mime_type="image/jpeg"):
        """Calls the Gemini API to perform OCR on the image bytes."""
        payload = {
            "contents": [
                {
                    "parts": [
                        { "text": "Perform OCR on this Thai bank transfer receipt. Return all text, including transaction ID, amount, date, and bank in its original language." },
                        {
                            "inlineData": {
                                "mimeType": image_mime_type,
                                "data": base64.b64encode(image_bytes).decode('utf-8')
                            }
                        }
                    ]
                }
            ],
            "config": { "systemInstruction": { "parts": [{ "text": "You are a specialized OCR model." }] } }
        }
        
        # Implement exponential backoff for reliability
        max_retries = 3
        delay = 2
        for i in range(max_retries):
            try:
                response = requests.post(GEMINI_API_URL, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
                response.raise_for_status() 
                result = response.json()
                
                text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                if text:
                    return text
                else:
                    print(f"OCR attempt {i+1} failed: No text returned.")
            except requests.exceptions.RequestException as e:
                print(f"OCR attempt {i+1} failed due to API error: {e}. Retrying in {delay}s...")
                if i < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
                else:
                    print("OCR failed after all retries.")
                    return "OCR_FAILED"
        return "OCR_FAILED"

    def handle_image_message(self, event):
        """Main handler for an incoming image message from LINE."""
        message_id = event.message.id
        reply_token = event.reply_token
        
        # 1. Get Image and Text
        try:
            message_content = LINE_BOT_API.get_message_content(message_id)
            image_bytes = message_content.content
        except Exception as e:
            LINE_BOT_API.reply_message(reply_token, TextMessage(text=f"ERROR: Could not download image content: {e}"))
            return

        # Use the event source text for caption/text extraction
        caption_text = event.message.text if hasattr(event.message, 'text') and event.message.text else ""
        
        # 2. Extract Admin Data from Caption
        unit_id = self._match_pattern(caption_text, 'unit_id')
        fee_month = self._match_pattern(caption_text, 'fee_month')
        email = self._match_pattern(caption_text, 'email')
        
        # 3. Perform OCR
        ocr_text = self._image_to_text(image_bytes)
        
        # 4. Extract Financial Data
        extracted_data = self._extract_receipt_data(ocr_text)

        # 5. Determine Status and Reply
        is_unit_valid = unit_id in self.valid_units
        is_complete = is_unit_valid and fee_month is not None and extracted_data['success']
        
        status = 'COMPLETED' if is_complete else 'PENDING_ADMIN_REVIEW'
        
        # Build the Firestore Record
        record = {
            'unit_id': unit_id if is_unit_valid else 'N/A',
            'fee_month': fee_month if fee_month else 'N/A',
            'email': email if email else 'N/A',
            'amount': extracted_data.get('amount'),
            'transaction_id': extracted_data.get('transaction_id'),
            'payer_name': extracted_data.get('payer_name'),
            'timestamp': datetime.now(),
            'status': status,
            'source_text': caption_text,
            'ocr_status': 'SUCCESS' if extracted_data['success'] else 'FAILED'
        }

        # 6. Save to Database
        try:
            if isinstance(self.db, firestore.client):
                self.db.collection(PAYMENTS_COLLECTION).add(record)
            else:
                self.db.collection(PAYMENTS_COLLECTION).set(record) # For Mock
        except Exception as e:
            reply_text = f"🚨 SYSTEM ERROR: Payment processed but failed to save to database. Admin must check manually. Error: {e}"
            LINE_BOT_API.reply_message(reply_token, TextMessage(text=reply_text))
            return
        
        # 7. Send Final Reply
        if is_complete:
            reply_text = (
                f"✅ Success! Your payment has been **automatically recorded**.\n\n"
                f"Unit: {unit_id}, Month: {fee_month}\n"
                f"Amount: {record['amount']:.2f} THB\n"
                f"Thank you for following the format. Your official receipt will be processed shortly."
            )
        else:
            missing = []
            if not is_unit_valid: missing.append("Unit ID (e.g., 88/75)")
            if fee_month is None: missing.append("Fee Month (e.g., 2025-11)")
            if not extracted_data['success']: missing.append("Clear financial data on receipt.")
            
            reply_text = (
                f"⚠️ Recorded for Review (PENDING)\n\n"
                f"We could not fully automate your record. Admin staff must verify.\n"
                f"Missing/Invalid Data: {', '.join(missing)}\n\n"
                f"Please ensure you send the **Unit ID, Fee Month, and Email** in the caption."
            )
            
        LINE_BOT_API.reply_message(reply_token, TextMessage(text=reply_text))


    def create_report_csv(self, payments_data):
        """Converts a list of payment dictionaries into a CSV file in memory."""
        if not payments_data:
            return None, 0

        # Define CSV header order
        fieldnames = [
            'timestamp', 'unit_id', 'fee_month', 'amount', 
            'transaction_id', 'payer_name', 'email', 'status', 
            'source_text', 'ocr_status'
        ]
        
        # Use StringIO to build the CSV string in memory
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        
        writer.writeheader()
        for payment in payments_data:
            # Format datetime for readability
            payment['timestamp'] = payment['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow(payment)

        return output.getvalue(), len(payments_data)

    def send_report_email(self, report_csv_data, recipient, start_time, end_time, count):
        """Sends the generated CSV data as an email attachment."""
        if not ADMIN_REPORT_EMAIL or not SMTP_PASSWORD:
            print("ERROR: Email credentials missing. Cannot send report.")
            return

        msg = MIMEMultipart()
        msg['From'] = ADMIN_REPORT_EMAIL
        msg['To'] = recipient
        
        subject_time_range = f"{start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}"
        msg['Subject'] = f"Payment Report: {count} New Transactions ({end_time.strftime('%Y-%m-%d')})"
        
        body = f"Attached is the CSV report containing {count} new COMPLETED payment records processed by the LINE OA system between {start_time.strftime('%Y-%m-%d %H:%M:%S')} and {end_time.strftime('%Y-%m-%d %H:%M:%S')}.\n\nThis report includes payments that were automatically processed and those manually marked as COMPLETED by an admin (if applicable)."
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach CSV
        part = MIMEApplication(report_csv_data, Name='payment_report.csv')
        part['Content-Disposition'] = f'attachment; filename="village_payments_{end_time.strftime("%Y%m%d_%H%M")}.csv"'
        msg.attach(part)
        
        # Send via SMTP
        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(ADMIN_REPORT_EMAIL, SMTP_PASSWORD)
            server.sendmail(ADMIN_REPORT_EMAIL, recipient, msg.as_string())
            server.quit()
            print(f"Successfully sent report email to {recipient} with {count} records.")
        except Exception as e:
            print(f"ERROR: Failed to send email via SMTP: {e}")

    def run_scheduled_report(self):
        """Queries database for new payments since last run, emails the report, and updates the timestamp."""
        
        # 1. Get the last report timestamp
        report_start_time = self._get_last_report_time()
        report_end_time = datetime.now()
        
        # 2. Query for new COMPLETED payments
        try:
            # Note: Firestore only allows one inequality filter ('timestamp' > report_start_time).
            # Sorting and filtering by status is necessary for the report.
            query = self.db.collection(PAYMENTS_COLLECTION).where('status', '==', 'COMPLETED').where('timestamp', '>', report_start_time).stream()
            payments_data = [doc.to_dict() for doc in query]
        except Exception as e:
            print(f"Database query error: {e}")
            return
            
        # 3. Create CSV
        csv_data, count = self.create_report_csv(payments_data)

        if count > 0 and csv_data:
            # 4. Email the report
            self.send_report_email(csv_data, ADMIN_REPORT_EMAIL, report_start_time, report_end_time, count)
        else:
            print(f"No new payments found since {report_start_time}. Email skipped.")
        
        # 5. Update the last report timestamp (even if 0 new payments were found)
        self._update_last_report_time(report_end_time)


# --- 5. SCHEDULER THREAD ---
def start_daily_email_scheduler(processor_instance, morning_hour=9, afternoon_hour=16):
    """Starts a background thread to check for scheduled report times."""
    
    def scheduler_loop():
        while True:
            now = datetime.now()
            current_hour = now.hour
            current_minute = now.minute

            # Check for Morning Report time (e.g., 9:00 AM)
            if current_hour == morning_hour and current_minute == 0:
                print(f"--- Triggering Morning Report ({morning_hour}:00) ---")
                processor_instance.run_scheduled_report()
                time.sleep(60) # Sleep for a minute to prevent double-trigger

            # Check for Afternoon Report time (e.g., 4:00 PM)
            elif current_hour == afternoon_hour and current_minute == 0:
                print(f"--- Triggering Afternoon Report ({afternoon_hour}:00) ---")
                processor_instance.run_scheduled_report()
                time.sleep(60) # Sleep for a minute to prevent double-trigger

            # Sleep for most of the minute, or a short time if near the hour mark
            sleep_time = 60 - now.second
            time.sleep(sleep_time if sleep_time > 5 else 5)

    print(f"Starting scheduled email reports for {morning_hour}:00 and {afternoon_hour}:00 (using Render server time, usually UTC).")
    thread = Thread(target=scheduler_loop)
    thread.daemon = True # Allows thread to exit when the main app exits
    thread.start()


# --- 6. FLASK WEB APPLICATION ---

app = flask.Flask(__name__)

# Initialize processor instance outside of requests
processor = ProductionLineOAProcessor(DB)

# Start the scheduler thread after the processor is initialized
start_daily_email_scheduler(processor, morning_hour=9, afternoon_hour=16) 


@app.route("/webhook", methods=['POST'])
def webhook():
    """Handles incoming LINE webhook events."""
    if not HANDLER:
        return 'LINE Handler not initialized', 500
        
    signature = flask.request.headers.get('X-Line-Signature')
    body = flask.request.get_data(as_text=True)
    
    try:
        HANDLER.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Check channel secret.")
        flask.abort(400)
    except Exception as e:
        print(f"Error handling request: {e}")
        flask.abort(500)
        
    return 'OK'

@HANDLER.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """Handles text messages (used when resident sends text AND image)."""
    # If a text message arrives, and it's not a reply to a previous message, 
    # we treat the text as the caption for the subsequent image, 
    # but the image handler will be the main logic.
    pass

@HANDLER.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    """Handles image messages, triggering the main OCR and saving logic."""
    print(f"Received Image Message from source type: {event.source.type}")
    processor.handle_image_message(event)

@app.route("/run-report", methods=['GET'])
def run_report_on_demand():
    """Endpoint for staff to manually trigger an immediate email report run."""
    print("--- Admin triggered ON-DEMAND Report ---")
    
    # Run the report in a separate thread so the HTTP request completes quickly
    thread = Thread(target=processor.run_scheduled_report)
    thread.start()
    
    return flask.jsonify({
        "status": "Report Triggered",
        "message": f"Report generation started. The CSV will be emailed to {ADMIN_REPORT_EMAIL} shortly.",
        "note": "Check your email for the attachment."
    }), 200

# Entry point for Render
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
