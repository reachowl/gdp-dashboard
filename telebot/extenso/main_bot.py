import logging
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, CallbackContext
)
from config import Config, Permissions 
from messages import Messages 
from database import db 
from staff_commands import BilingualStaffCommands 
import datetime

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
        # Default to 'en'
        return 'en'

    # ==================== A. RESIDENT COMMANDS ====================

    async def start(self, update: Update, context: CallbackContext) -> None:
        """Sends a welcome message and language selection."""
        user = update.effective_user
        lang = self.get_user_language(user.id)

        keyboard = [
            [InlineKeyboardButton("English 🇬🇧", callback_data='lang_en')],
            [InlineKeyboardButton("ภาษาไทย 🇹🇭", callback_data='lang_th')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = Messages.get_message('welcome', lang)
        
        # Append staff dashboard message if applicable
        if Permissions.is_admin(user.id):
            welcome_text += "\n\n" + Messages.get_message('welcome_admin', lang)
        elif Permissions.is_operator(user.id):
            welcome_text += "\n\n" + Messages.get_message('welcome_operator', lang)

        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def check_balance(self, update: Update, context: CallbackContext) -> None:
        """
        Handles the /balance command, showing the resident's current balance.
        """
        user_id = update.effective_user.id
        
        # 1. Get resident info and language
        resident_info = db.get_resident_balance_by_telegram_id(user_id)
        
        # 2. Check registration
        if not resident_info:
            lang = self.get_user_language(user_id)
            await update.message.reply_text(Messages.get_message('not_registered', lang))
            return
            
        lang = resident_info['language']
        unit = resident_info['unit']
        # Balance is stored in 'cents' (e.g., 50000 = ฿500.00)
        balance = resident_info['current_balance'] 
        
        # Convert balance to major currency unit for display
        display_balance = balance / 100.0 

        # 3. Determine balance status and message key
        # 'balance_credit': balance >= 0 (In credit or exactly zero)
        # 'balance_debt': balance < 0 (In debt)
        status_key = 'balance_credit' if display_balance >= 0 else 'balance_debt' 
            
        # 4. Format and send the message
        message = Messages.get_message(
            status_key, 
            lang, 
            unit=unit, 
            balance_abs=abs(display_balance) # Pass absolute value for formatting
        )

        await update.message.reply_text(message, parse_mode='Markdown')

    # ==================== B. REGISTRATION CONVERSATION ====================

    async def register_start(self, update: Update, context: CallbackContext) -> int:
        """Starts the registration process by prompting for unit number."""
        user_id = update.effective_user.id
        lang = self.get_user_language(user_id)
        
        # Check if the user used /register with an argument
        text = update.message.text.strip()
        match = re.match(r'\/register\s+([A-Za-z0-9\/]+)', text)
        
        if match:
            # If unit is provided, proceed directly to unit validation
            update.message.text = text # Ensure text is still available for receive_unit
            return await self.receive_unit(update, context)
        else:
            # If no unit is provided, prompt for it
            await update.message.reply_text(Messages.get_message('register_prompt', lang), parse_mode='Markdown')
            # Use UNIT_ENTRY state to handle the next message as the unit number
            return UNIT_ENTRY


    async def receive_unit(self, update: Update, context: CallbackContext) -> int:
        """Receives the unit number and checks if it's valid."""
        user_id = update.effective_user.id
        lang = self.get_user_language(user_id)
        
        # Expected input: 88/01 or /register 88/01 (handled by register_start)
        text = update.message.text.strip()
        
        # Extract unit number only if it was not passed via the command
        unit_input = text
        match = re.match(r'\/register\s+([A-Za-z0-9\/]+)', text)
        if match:
            unit_input = match.group(1)
            
        unit = unit_input.upper() # Normalize unit to uppercase

        # 1. Check if the unit exists in the master data
        resident_data = db.get_resident_by_unit(unit)
        if not resident_data:
            await update.message.reply_text(Messages.get_message('unit_not_found', lang, unit=unit))
            # Keep in the same state to allow retrying
            return UNIT_ENTRY 

        # 2. Store unit and prompt for PIN
        context.user_data['unit'] = unit
        await update.message.reply_text(Messages.get_message('pin_prompt', lang, unit=unit), parse_mode='Markdown')
        return PIN_ENTRY

    async def receive_pin(self, update: Update, context: CallbackContext) -> int:
        """Receives the PIN and attempts to complete registration."""
        user = update.effective_user
        user_id = user.id
        lang = self.get_user_language(user_id)
        
        # 1. Retrieve stored unit and input PIN
        unit = context.user_data.get('unit')
        pin = update.message.text.strip()

        if not unit:
            await update.message.reply_text(Messages.get_message('generic_error', lang))
            return ConversationHandler.END

        # 2. PIN validation logic (Placeholder logic: must be '1234')
        is_pin_valid = pin == '1234' 

        if not is_pin_valid:
            await update.message.reply_text(Messages.get_message('pin_invalid', lang))
            return PIN_ENTRY # Stay in PIN entry state

        # 3. Successful registration
        user_name = user.username or f"{user.first_name} {user.last_name or ''}".strip()
        
        registration_success = db.update_resident_registration(unit, user_id, user_name, lang)

        if registration_success:
            await update.message.reply_text(Messages.get_message('registration_success', lang, unit=unit), parse_mode='Markdown')
        else:
            await update.message.reply_text(Messages.get_message('generic_error', lang))

        # Clear context data and end conversation
        context.user_data.clear()
        return ConversationHandler.END

    # ==================== C. PAYMENT CONVERSATION ====================

    async def report_payment_start(self, update: Update, context: CallbackContext) -> int:
        """Starts the payment reporting process."""
        user_id = update.effective_user.id
        
        # Check if user is registered first
        resident = db.get_resident_by_telegram(user_id)
        if not resident:
            lang = self.get_user_language(user_id)
            await update.message.reply_text(Messages.get_message('not_registered', lang))
            return ConversationHandler.END
            
        lang = resident.get('language', 'en')
        context.user_data['lang'] = lang
        context.user_data['unit'] = resident['unit']

        await update.message.reply_text(Messages.get_message('payment_start', lang), parse_mode='Markdown')
        return RECEIPT_UPLOAD

    async def receive_receipt_photo(self, update: Update, context: CallbackContext) -> int:
        """Receives the photo receipt."""
        lang = context.user_data.get('lang', 'en')
        
        # 1. Get the file and save it
        photo_file = await update.message.photo[-1].get_file()
        file_extension = ".jpg" 
        
        # Generate a unique filename: unit_timestamp_telegramid.jpg
        unit = context.user_data['unit']
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{unit}_{timestamp}_{update.effective_user.id}{file_extension}"
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        
        await photo_file.download_to_drive(filepath)
        
        context.user_data['receipt_filename'] = filename
        
        # 2. Prompt for payment details
        await update.message.reply_text(Messages.get_message('payment_details_prompt', lang), parse_mode='Markdown')
        return DETAILS_ENTRY

    async def receive_payment_details(self, update: Update, context: CallbackContext) -> int:
        """Receives payment details (amount and reference) and logs the payment."""
        lang = context.user_data.get('lang', 'en')
        unit = context.user_data.get('unit')
        receipt_filename = context.user_data.get('receipt_filename')
        
        details_text = update.message.text.strip()
        
        # Expected details format: Amount, Reference (e.g., "500.00, Maintenance Fee")
        try:
            parts = [p.strip() for p in details_text.split(',', 1)]
            amount_str = parts[0]
            reference = parts[1] if len(parts) > 1 else Messages.get_message('payment_default_ref', lang)
            
            # Remove commas and convert to float, then to integer (for storage)
            amount_float = float(amount_str.replace(',', ''))
            amount_stored = int(round(amount_float * 100)) # Store as cents (satangs)

            if amount_stored <= 0:
                 raise ValueError("Amount must be positive.")
            
        except (ValueError, IndexError):
            await update.message.reply_text(Messages.get_message('payment_details_invalid', lang), parse_mode='Markdown')
            return DETAILS_ENTRY # Stay in this state

        # 1. Save payment to DB
        payment_id = db.add_payment(
            unit=unit, 
            amount=amount_stored, 
            reference=reference, 
            receipt_filename=receipt_filename, 
            telegram_user_id=update.effective_user.id,
            language=lang
        )

        # 2. Send notification to staff log channel
        await self.staff_commands.send_payment_notification(context.bot, payment_id, lang=lang)

        # 3. Confirm to resident
        await update.message.reply_text(
            Messages.get_message(
                'payment_success', 
                lang, 
                unit=unit, 
                amount=amount_stored/100.0, # Pass float for formatting
                ref=reference
            ), 
            parse_mode='Markdown'
        )

        # 4. Clear context and end conversation
        context.user_data.clear()
        return ConversationHandler.END

    # ==================== D. SHARED/UTILITY HANDLERS ====================

    async def button_handler(self, update: Update, context: CallbackContext) -> None:
        """Handles non-staff related callback queries (e.g., language selection)."""
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if query.data.startswith('lang_'):
            new_lang = query.data.split('_')[1]
            
            # Only update language if resident is registered
            resident = db.get_resident_by_telegram(user_id)
            if resident:
                # Use the existing unit and name to update registration with new language
                db.update_resident_registration(resident['unit'], user_id, resident['telegram_name'], new_lang)
            
            await query.edit_message_text(
                Messages.get_message('language_set', new_lang),
                reply_markup=None
            )
        
    async def handle_resident_message(self, update: Update, context: CallbackContext) -> None:
        """
        Catches all non-command messages from registered residents and logs them 
        as a support query, then notifies staff.
        """
        user_id = update.effective_user.id
        resident = db.get_resident_by_telegram(user_id)
        
        # Only process messages from registered users who are NOT staff
        if resident and not Permissions.is_operator(user_id):
            message_text = update.message.text
            lang = resident.get('language', 'en')
            
            # 1. Log the message
            db.log_support_message(user_id, 'RESIDENT_MESSAGE', message_text)
            
            # 2. Send notification to staff log group
            await self.staff_commands.send_support_notification(
                context.bot, 
                user_id, 
                resident['unit'], 
                message_text
            )
            
            # 3. Respond to resident (this is their confirmation)
            await update.message.reply_text(Messages.get_message('support_received', lang), parse_mode='Markdown')
            
        elif not Permissions.is_operator(user_id) and update.message.text:
            # Non-registered user sending non-command text
            lang = self.get_user_language(user_id)
            await update.message.reply_text(Messages.get_message('not_registered', lang))


    async def cancel_conversation(self, update: Update, context: CallbackContext) -> int:
        """Cancels and ends the current conversation."""
        user_id = update.effective_user.id
        lang = self.get_user_language(user_id)
        
        await update.message.reply_text(Messages.get_message('conversation_cancelled', lang))
        
        # Clear context data
        context.user_data.clear()
        return ConversationHandler.END

# --- Main Bot Setup ---

def main():
    """Start the bot."""
    if not Config.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in config.py or .env file.")
        return
        
    application = Application.builder().token(Config.BOT_TOKEN).build()
    dispatcher = application.dispatcher
    main_bot = BilingualExtensoBot()
    staff_commands = main_bot.staff_commands
    
    # A. BASIC COMMANDS
    dispatcher.add_handler(CommandHandler('start', main_bot.start))
    dispatcher.add_handler(CommandHandler('balance', main_bot.check_balance))

    # B. STAFF COMMANDS
    # Note: These are implemented as stubs in staff_commands.py, but handlers are registered here.
    dispatcher.add_handler(CommandHandler('pending', staff_commands.pending_payments))
    dispatcher.add_handler(CommandHandler('reply', staff_commands.reply_to_resident))
    dispatcher.add_handler(CommandHandler('dashboard', staff_commands.admin_dashboard))
    dispatcher.add_handler(CommandHandler('broadcast', staff_commands.broadcast_announcement))
    dispatcher.add_handler(CommandHandler('remind', staff_commands.payment_reminder))

    # C. REGISTRATION CONVERSATION HANDLER
    registration_handler = ConversationHandler(
        # Allow /register (with or without argument) to start the conversation
        entry_points=[CommandHandler('register', main_bot.register_start)],
        states={
            UNIT_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_bot.receive_unit)],
            PIN_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_bot.receive_pin)]
        },
        fallbacks=[CommandHandler('cancel', main_bot.cancel_conversation)],
        allow_reentry=True
    )
    dispatcher.add_handler(registration_handler) 

    # D. PAYMENT CONVERSATION HANDLER
    payment_handler = ConversationHandler(
        entry_points=[CommandHandler('payment', main_bot.report_payment_start)],
        states={
            RECEIPT_UPLOAD: [MessageHandler(filters.PHOTO & ~filters.COMMAND, main_bot.receive_receipt_photo)],
            DETAILS_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_bot.receive_payment_details)]
        },
        fallbacks=[CommandHandler('cancel', main_bot.cancel_conversation)],
        allow_reentry=True
    )
    dispatcher.add_handler(payment_handler) 

    # E. CALLBACK QUERY HANDLERS
    dispatcher.add_handler(CallbackQueryHandler(staff_commands.handle_payment_callback, pattern='^(approve|reject|receipt)_'))
    dispatcher.add_handler(CallbackQueryHandler(main_bot.button_handler))

    # F. RESIDENT MESSAGE HANDLER (CATCH-ALL FOR SUPPORT)
    # This handler must come AFTER all other specific command and conversation handlers
    dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_bot.handle_resident_message))


    # G. Start the Bot
    print("Starting ExtensoBot polling...")
    application.run_polling(poll_interval=1.0)

if __name__ == '__main__':
    # Increase recursion limit for complex ConversationHandler structures (optional, but good practice)
    import sys
    sys.setrecursionlimit(2000)
    main()
