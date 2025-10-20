# config.py (Updated)

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration settings loaded from environment variables."""
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # Staff permissions (Ensure your .env file uses comma-separated IDs if multiple)
    ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
    OPERATOR_IDS = [int(x.strip()) for x in os.getenv('OPERATOR_IDS', '').split(',') if x.strip()]
    
    # Language preferences for staff
    ENGLISH_STAFF_IDS = [int(x.strip()) for x in os.getenv('ENGLISH_STAFF_IDS', '').split(',') if x.strip()]
    THAI_STAFF_IDS = [int(x.strip()) for x in os.getenv('THAI_STAFF_IDS', '').split(',') if x.strip()]
    
    # Communication Channels
    BROADCAST_CHANNEL = os.getenv('BROADCAST_CHANNEL', '@ExtensoVillageAnnouncements')

    # Support Log Group ID (Must be a numerical chat ID, usually starting with -100)
    STAFF_LOG_CHAT_ID = int(os.getenv('STAFF_LOG_CHAT_ID', '-1001234567890'))
    
    # Database and Files
    DATABASE_URL = 'sqlite:///extenso_village.db' # Not directly used by sqlite3, but descriptive
    UPLOAD_FOLDER = 'receipts'
    DATA_FOLDER = 'data' # For storing DB file and general data

class Permissions:
    """Static methods to check user permissions and apply decorators."""

    @staticmethod
    def is_admin(user_id: int) -> bool:
        """Check if a user is an admin."""
        return user_id in Config.ADMIN_IDS
    
    @staticmethod
    def is_operator(user_id: int) -> bool:
        """Check if a user is an operator or an admin."""
        return user_id in Config.OPERATOR_IDS or user_id in Config.ADMIN_IDS
    
    @staticmethod
    def is_registered(user_id: int) -> bool:
        """Check if a user is a registered resident (requires database lookup, implemented elsewhere)."""
        # This function is a placeholder; actual check is in the bot logic.
        return False
    
    @staticmethod
    def require_admin(func):
        """Decorator to restrict command to administrators."""
        def wrapper(update, context):
            if update.effective_user and not Permissions.is_admin(update.effective_user.id):
                # Import inside to avoid circular dependency with messages.py
                from messages import Messages
                # Determine language for the error message
                lang = 'th' if update.effective_user.id in Config.THAI_STAFF_IDS else 'en'
                update.message.reply_text(Messages.get_message('admin_access_required', lang))
                return
            return func(update, context)
        return wrapper
    
    @staticmethod
    def require_operator(func):
        """Decorator to restrict command to operators and administrators."""
        def wrapper(update, context):
            if update.effective_user and not Permissions.is_operator(update.effective_user.id):
                # Import inside to avoid circular dependency with messages.py
                from messages import Messages
                # Determine language for the error message
                lang = 'th' if update.effective_user.id in Config.THAI_STAFF_IDS else 'en'
                update.message.reply_text(Messages.get_message('staff_access_required', lang))
                return
            return func(update, context)
        return wrapper

    @staticmethod
    def require_registered(func):
        """Decorator to restrict command to registered residents."""
        def wrapper(update, context):
            user_id = update.effective_user.id
            # Import inside to avoid circular dependency with database.py/messages.py
            from database import db
            from messages import Messages
            
            resident = db.get_resident_by_telegram(user_id)
            if not resident:
                # Use default language 'en' if resident is not found, or infer from command language
                lang = 'en' # Default language for non-registered users
                update.message.reply_text(Messages.get_message('not_registered', lang))
                return
            
            return func(update, context)
        return wrapper
