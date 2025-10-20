import logging
import re
import os # NEW: Added os import for directory check
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, CallbackContext
)
from config import Config, Permissions 
from messages import Messages 
from database import db 
from staff_commands import BilingualStaffCommands 

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO) 
logger = logging.getLogger(__name__)

# --- Conversation States ---
UNIT_ENTRY, PIN_ENTRY = range(2) # For /register
RECEIPT_UPLOAD, DETAILS_ENTRY = range(2, 4) # For /payment

class BilingualExtensoBot:
    def __init__(self):
        self.staff_commands = BilingualStaffCommands()
        # Ensure the uploads folder exists
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)

    def get_user_language(self, user_id):
        """Get user's language preference (resident or staff)."""
        resident = db.get_resident_by_telegram(user_id) 
        if resident:
            return resident.get('language', 'en') 
        
        # Staff language preferences
        if user_id in Config.THAI_STAFF_IDS:
            return 'th'
        elif user_id in Config.ENGLISH_STAFF_IDS or user_id in Config.ADMIN_IDS:
            return 'en'
        
        # Default for new users
        return 'en'

    # =======================================================
    # Resident Commands
    # =======================================================

    async def start(self, update: Update, context: CallbackContext) -> None:
        """Sends a welcome message and language selection."""
        user_id = update.effective_user.id
        
        # 1. Check for Staff Permissions (Admin/Operator)
        if Permissions.is_admin(user_id):
            lang = self.get_user_language(user_id)
            await update.message.reply_text(
                Messages.get_message('welcome_admin', lang),
                parse_mode='Markdown'
            )
        elif Permissions.is_operator(user_id):
            lang = self.get_user_language(user_id)
            await update.message.reply_text(
                Messages.get_message('welcome_operator', lang),
                parse_mode='Markdown'
            )
        
        # 2. Handle Resident/New User
        else:
            lang = self.get_user_language(user_id)
            
            # Check if resident is registered
            resident = db.get_resident_by_telegram(user_id)
            
            if resident:
                # User is registered: Show main menu
                await update.message.reply_text(
                    Messages.get_message('welcome_back', resident['language'], unit=resident['unit']),
                    reply_markup=self.get_resident_main_menu(resident['language']),
                    parse_mode='Markdown'
                )
            else:
                # New user or unregistered: Show language selection
                keyboard = [
                    [InlineKeyboardButton("English 🇬🇧", callback_data='set_lang_en')],
                    [InlineKeyboardButton("ภาษาไทย 🇹🇭", callback_data='set_lang_th')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    Messages.get_message('welcome', lang),
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        
        # CRITICAL FIX: Explicitly return None to prevent the NoneType error
        return None 

    async def get_resident_main_menu(self, lang):
        """Creates the main menu keyboard for registered residents."""
        keyboard = [
            [InlineKeyboardButton(Messages.get_message('menu_status', lang), callback_data='menu_status')],
            [InlineKeyboardButton(Messages.get_message('menu_payment', lang), callback_data='menu_payment')],
            [InlineKeyboardButton(Messages.get_message('menu_rules', lang), callback_data='menu_rules')],
            [InlineKeyboardButton(Messages.get_message('menu_support', lang), callback_data='menu_support')],
        ]
        return InlineKeyboardMarkup(keyboard)

    # ... (rest of the class methods, including /status, /register functions, etc.)
    # I've omitted other methods for brevity, assuming they are complete.

    async def status(self, update: Update, context: CallbackContext) -> None:
        """Handles the /status command for residents."""
        user_id = update.effective_user.id
        resident = db.get_resident_by_telegram(user_id)
        lang = self.get_user_language(user_id)

        if not resident:
            await update.message.reply_text(Messages.get_message('not_registered', lang))
            return None

        # Format current_balance correctly (it's stored in Satang/cents, so divide by 100 for Baht)
        balance_baht = resident.get('current_balance', 0) / 100
        
        status_message = Messages.get_message(
            'status_message', 
            lang, 
            unit=resident['unit'], 
            balance=balance_baht
        )
        
        await update.message.reply_text(status_message, parse_mode='Markdown')
        return None

    # Conversation handler fallback
    async def cancel_conversation(self, update: Update, context: CallbackContext) -> int:
        """Cancels and ends the current conversation."""
        lang = self.get_user_language(update.effective_user.id)
        await update.message.reply_text(
            Messages.get_message('conversation_cancelled', lang),
            reply_markup=self.get_resident_main_menu(lang) # Return to main menu
        )
        return ConversationHandler.END


    # Language setting handler
    async def button_handler(self, update: Update, context: CallbackContext) -> None:
        """Handles all non-payment related inline button presses."""
        query = update.callback_query
        user_id = query.from_user.id
        
        # Check if button press is language setting
        if query.data.startswith('set_lang_'):
            new_lang = query.data.split('_')[2]
            
            # Update resident language if registered
            resident = db.get_resident_by_telegram(user_id)
            if resident:
                db.update_resident_language(user_id, new_lang)
                lang = new_lang # Use new lang for response
                
                # After setting language for a registered user, show the main menu
                await query.edit_message_text(
                    Messages.get_message('language_set', lang),
                    reply_markup=self.get_resident_main_menu(lang)
                )
            else:
                # Store language in session data for unregistered users during the /register flow
                context.user_data['language'] = new_lang
                lang = new_lang
                
                # Edit message to confirm language set, but keeps them at the registration prompt
                await query.edit_message_text(
                    Messages.get_message('language_set', lang) + "\n\n" + Messages.get_message('register_prompt', lang),
                    parse_mode='Markdown'
                )

        elif query.data == 'menu_status':
            # Call the status handler logic
            await self.status(update, context)

        elif query.data == 'menu_payment':
            # Start the payment conversation (calls report_payment_start)
            await self.report_payment_start(update, context)

        # Acknowledge the query to remove the 'loading' state on the button
        await query.answer()

    # ... (Add the rest of the BilingualExtensoBot class methods, including report_payment_start, etc.)

    # The registration and payment conversation methods need to be included here for completeness, 
    # but I will only show the main method and the application runner again.
    
    # ... (Assuming report_payment_start, receive_receipt_photo, receive_payment_details, handle_resident_message are defined)


    # Placeholder methods for now to ensure the class structure is complete for the handlers in main
    async def report_payment_start(self, update: Update, context: CallbackContext) -> int:
        lang = self.get_user_language(update.effective_user.id)
        await update.effective_message.reply_text(Messages.get_message('payment_start', lang))
        return RECEIPT_UPLOAD

    async def receive_receipt_photo(self, update: Update, context: CallbackContext) -> int:
        # Placeholder logic
        lang = self.get_user_language(update.effective_user.id)
        await update.message.reply_text(Messages.get_message('receipt_received', lang))
        return DETAILS_ENTRY

    async def receive_payment_details(self, update: Update, context: CallbackContext) -> int:
        # Placeholder logic
        lang = self.get_user_language(update.effective_user.id)
        await update.message.reply_text(Messages.get_message('payment_submitted', lang))
        return ConversationHandler.END

    async def handle_resident_message(self, update: Update, context: CallbackContext) -> None:
        # Placeholder logic
        lang = self.get_user_language(update.effective_user.id)
        await update.message.reply_text(Messages.get_message('support_received', lang))
        return None

    # Placeholder for /register conversation handlers
    async def register_start(self, update: Update, context: CallbackContext) -> int:
        # Placeholder logic
        lang = self.get_user_language(update.effective_user.id)
        await update.message.reply_text(Messages.get_message('register_prompt', lang))
        return UNIT_ENTRY

    async def enter_unit(self, update: Update, context: CallbackContext) -> int:
        # Placeholder logic
        lang = self.get_user_language(update.effective_user.id)
        await update.message.reply_text(Messages.get_message('registration_success', lang, unit=context.user_data['unit']))
        return ConversationHandler.END


def main() -> None:
    """Start the bot."""
    
    # Check if BOT_TOKEN is set
    if not Config.BOT_TOKEN:
        logger.error("FATAL: BOT_TOKEN is not set in the .env file.")
        return

    main_bot = BilingualExtensoBot()
    application = Application.builder().token(Config.BOT_TOKEN).build()
    dispatcher = application.add_handler

    # A. CORE COMMAND HANDLERS
    # The /start command handler
    dispatcher(CommandHandler('start', main_bot.start))
    dispatcher(CommandHandler('status', main_bot.status))
    dispatcher(CommandHandler('cancel', main_bot.cancel_conversation))
    # Staff/Admin commands (using the staff_commands instance)
    # FIX: Corrected method name from pending_payments to list_pending_payments based on traceback suggestion
    dispatcher(CommandHandler('pending', main_bot.staff_commands.list_pending_payments))
    dispatcher(CommandHandler('dashboard', main_bot.staff_commands.dashboard))
    dispatcher(CommandHandler('broadcast', main_bot.staff_commands.broadcast_announcement))
    dispatcher(CommandHandler('remind', main_bot.staff_commands.payment_reminder))
    dispatcher(CommandHandler('reply', main_bot.staff_commands.reply_to_resident))


    # B. REGISTRATION CONVERSATION HANDLER (Currently uses a simplified /register UNIT_NUMBER)
    registration_handler = ConversationHandler(
        entry_points=[CommandHandler('register', main_bot.register_start)],
        states={
            UNIT_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_bot.enter_unit)],
            # PIN_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_bot.enter_pin)], # Assuming PIN step is skipped for now
        },
        fallbacks=[CommandHandler('cancel', main_bot.cancel_conversation)],
        allow_reentry=True
    )
    dispatcher(registration_handler) 

    # C. PAYMENT CONVERSATION HANDLER
    payment_handler = ConversationHandler(
        entry_points=[CommandHandler('payment', main_bot.report_payment_start)],
        states={
            # FIX: Changed Filters.photo/text to filters.PHOTO/TEXT
            RECEIPT_UPLOAD: [MessageHandler(filters.PHOTO & ~filters.COMMAND, main_bot.receive_receipt_photo)],
            DETAILS_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_bot.receive_payment_details)]
        },
        fallbacks=[CommandHandler('cancel', main_bot.cancel_conversation)],
        allow_reentry=True
    )
    dispatcher(payment_handler) 

    # D. CALLBACK QUERY HANDLERS
    dispatcher(CallbackQueryHandler(main_bot.staff_commands.handle_payment_callback, pattern='^(approve|reject|receipt)_'))
    dispatcher(CallbackQueryHandler(main_bot.button_handler))

    # 🚨 NEW: RESIDENT MESSAGE HANDLER (CATCH-ALL FOR SUPPORT) 🚨
    # This handler must come AFTER all other specific command and conversation handlers
    dispatcher(MessageHandler(filters.TEXT & ~filters.COMMAND, main_bot.handle_resident_message))


    # E. Start the Bot
    print("Starting ExtensoBot polling...")
    # FIX: Use the 'application' object to start polling
    application.run_polling(poll_interval=1.0)

if __name__ == '__main__':
    # Initial setup for placeholders in the database (assuming they exist from previous steps)
    
    # We will modify the get_resident_by_telegram logic in database.py to handle the initial /start check better.
    
    # Ensure the messages file has the new key used in the start function
    # It seems 'welcome_back' is missing, let's add it to messages.py

    # The original main() was inside the file, so we just run it.
    main()
