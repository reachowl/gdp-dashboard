import os
import json
from flask import Flask, redirect, url_for, render_template, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, ButtonsTemplate, PostbackAction, URIAction, MessageAction, RichMenu
from linebot.exceptions import InvalidSignatureError
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import datetime
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# --- 1. ENVIRONMENT & CONFIGURATION ---

# All secrets are read securely from Render's Environment Variables
FLASK_SECRET = os.environ.get('FLASK_SECRET_KEY')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ID = os.environ.get('LINE_CHANNEL_ID')
DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')
SERVICE_ACCOUNT_JSON = os.environ.get('GOOGLE_SERVICE_ACCOUNT_CREDENTIALS')

# Initialize Flask/Dash App
app = Flask(__name__)
app.config['SECRET_KEY'] = FLASK_SECRET
app.config['DEBUG'] = False # Render manages debug state

# Initialize LINE Bot
line_bot_api = LineBotApi(os.environ.get('LINE_ACCESS_TOKEN'))
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Database Setup (Temporary SQLite for Trial)
# The "sqlite:////" prefix is required by SQLAlchemy for an absolute path.
# We use the /tmp/ directory because it is guaranteed to be writable on Render.
default_db_path = 'sqlite:////tmp/village.db' 
DATABASE_PATH = os.environ.get('DATABASE_FILE_PATH', default_db_path)
engine = create_engine(DATABASE_PATH)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# --- 2. DATABASE MODEL (User and Units) ---

class Resident(Base):
    __tablename__ = 'residents'
    id = Column(Integer, primary_key=True)
    line_user_id = Column(String, unique=True, nullable=False)
    unit_number = Column(String, unique=True, nullable=False)
    size_sqm = Column(Float, nullable=False)
    pin_code = Column(String, nullable=False) # Secret PIN for linking

    def __repr__(self):
        return f"<Resident(Unit={self.unit_number}, LineID={self.line_user_id})>"

class Receipt(Base):
    __tablename__ = 'receipts'
    id = Column(Integer, primary_key=True)
    unit_number = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    file_id = Column(String, nullable=False) # Google Drive File ID
    file_name = Column(String, nullable=False)

    def __repr__(self):
        return f"<Receipt(Unit={self.unit_number}, File={self.file_name})>"

# Create tables if they don't exist
Base.metadata.create_all(engine)

# --- 3. GOOGLE DRIVE SERVICE ---

def get_drive_service():
    """Initializes the Google Drive Service using the JSON credentials."""
    try:
        # Load the JSON string from the environment variable
        creds_info = json.loads(SERVICE_ACCOUNT_JSON)
        
        # Define the scope (access permissions)
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        
        # Build credentials object
        credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        
        # Build the Drive service
        service = build('drive', 'v3', credentials=credentials)
        return service
    except Exception as e:
        print(f"Error initializing Google Drive Service: {e}")
        return None

def upload_receipt_to_drive(file_data, mime_type, filename):
    """Uploads a file stream to the specified Google Drive folder."""
    drive_service = get_drive_service()
    if not drive_service:
        return False, "Failed to connect to Google Drive."

    file_metadata = {
        'name': filename,
        'parents': [DRIVE_FOLDER_ID]
    }
    
    # Use MediaIoBaseUpload for in-memory upload
    media = MediaIoBaseUpload(io.BytesIO(file_data),
                              mimetype=mime_type,
                              resumable=True)
    
    try:
        file = drive_service.files().create(body=file_metadata,
                                             media_body=media,
                                             fields='id').execute()
        return True, file.get('id')
    except Exception as e:
        print(f"File upload failed: {e}")
        return False, str(e)


# --- 4. FLASK ROUTES (LINE Webhook and Auth) ---

@app.route("/webhook", methods=['POST'])
def webhook():
    """Handles messages and events coming from LINE."""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Check your channel access token/secret.")
        return 'Invalid signature', 400
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """Handles text messages from users."""
    user_id = event.source.user_id
    text = event.message.text
    session = Session()
    resident = session.query(Resident).filter_by(line_user_id=user_id).first()
    session.close()

    if not resident:
        # User not linked, prompt for linking
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="Welcome! Please tap the button below to link your LINE account to your Unit Number using your 4-digit PIN.")
        )
        return

    # User is linked, handle specific commands
    if "RECEIPT" in text.upper():
        reply_message = "Please send a photo or PDF of your maintenance fee receipt to upload it to the Village records."
    elif "STATUS" in text.upper():
        reply_message = f"Hello Unit {resident.unit_number}. You are linked and ready to submit documents. Your registered size is {resident.size_sqm} sqm."
    else:
        reply_message = "I didn't recognize that command. Try typing 'RECEIPT' or 'STATUS'."

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_message)
    )

@handler.add(MessageEvent, message=(lambda msg: msg.type in ['image', 'document']))
def handle_file_message(event):
    """Handles image or document (receipt) uploads."""
    user_id = event.source.user_id
    session = Session()
    resident = session.query(Resident).filter_by(line_user_id=user_id).first()
    session.close()

    if not resident:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="Please link your account first before submitting documents."))
        return

    message_content = line_bot_api.get_message_content(event.message.id)
    file_data = message_content.content
    
    # Determine file details
    mime_type = event.message.type
    extension = ".jpg" if mime_type == 'image' else ".pdf"
    
    # Generate unique filename: Unit_Date_Time.ext
    timestamp = datetime.datetime.now()
    filename = f"{resident.unit_number}_{timestamp.strftime('%Y%m%d_%H%M%S')}{extension}"

    # Upload to Google Drive
    success, result = upload_receipt_to_drive(file_data, mime_type, filename)

    if success:
        # Save record to database
        session = Session()
        new_receipt = Receipt(
            unit_number=resident.unit_number,
            file_id=result,
            file_name=filename
        )
        session.add(new_receipt)
        session.commit()
        session.close()

        reply_text = f"✅ Success! Receipt for Unit {resident.unit_number} has been uploaded and secured in Google Drive.\nDrive File ID: {result}"
    else:
        reply_text = f"❌ Error during upload. Please notify village IT. Details: {result}"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))


# --- 5. INITIAL DATA SETUP (FOR TRIAL) ---

@app.cli.command('initdb')
def initdb_command():
    """Initializes/resets database and populates initial user data."""
    Base.metadata.drop_all(engine) # WARNING: Drops all tables!
    Base.metadata.create_all(engine)
    
    session = Session()
    # Add temporary unit data for trial (Unit/Size/PIN)
    # REPLACE WITH YOUR ACTUAL VILLAGE DATA
    trial_units = [
        Resident(unit_number='A-101', size_sqm=120.5, pin_code='1234'),
        Resident(unit_number='B-205', size_sqm=150.0, pin_code='5678'),
        Resident(unit_number='C-303', size_sqm=100.2, pin_code='9012'),
    ]
    session.add_all(trial_units)
    session.commit()
    session.close()
    print("Database initialized with trial units (A-101/1234, B-205/5678, C-303/9012).")

# --- Final Step: Commit Code to Git ---
# After pasting, commit and push this file to trigger the second, successful Render build.