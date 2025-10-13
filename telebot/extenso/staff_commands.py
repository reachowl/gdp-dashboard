import re
import os 
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import CallbackContext
from config import Config, Permissions 
from database import db # Use the shared db instance 
from messages import Messages 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class BilingualStaffCommands:
    def get_user_language(self, user_id: int) -> str:
        """
        Get staff member's preferred language based on config lists.
        Defaults to 'th' for Thai operators and 'en' for English staff/admins.
        """
        if user_id in Config.THAI_STAFF_IDS:
            return 'th'
        elif user_id in Config.ADMIN_IDS or user_id in Config.ENGLISH_STAFF_IDS:
            return 'en'
        return 'th'
    
    # ==================== GENERIC DASHBOARD (FIX FOR AttributeError) ====================

    @Permissions.require_operator
    async def dashboard(self, update: Update, context: CallbackContext) -> None:
        """
        Handles the /dashboard command for all staff (Admin or Operator).
        Sends the appropriate welcome message based on the user's highest role.
        This replaces the old admin_dashboard stub.
        """
        user_id = update.effective_user.id
        lang = self.get_user_language(user_id)
        
        # Determine the appropriate welcome message based on permission level
        if Permissions.is_admin(user_id):
            message_key = 'welcome_admin'
        else: # Must be an operator (checked by the @Permissions.require_operator decorator)
            message_key = 'welcome_operator'
            
        await update.message.reply_text(
            Messages.get_message(message_key, lang), 
            parse_mode='Markdown'
        )
    
    # ==================== PENDING PAYMENTS COMMAND ====================

    @Permissions.require_operator
    async def list_pending_payments(self, update: Update, context: CallbackContext) -> None:
        """Lists all pending payments for staff review."""
        user_id = update.effective_user.id
        lang = self.get_user_language(user_id)
        
        pending_payments = db.get_pending_payments() # Get payments where status='pending'
        
        if not pending_payments:
            await update.message.reply_text(Messages.get_message('no_pending_payments', lang))
            return

        # 1. Send the header
        await update.message.reply_text(
            Messages.get_message('pending_payments_count', lang, count=len(pending_payments)), 
            parse_mode='Markdown'
        )
        
        # 2. Iterate through payments and send a message for each one
        for payment in pending_payments:
            # Format the payment message
            message_text = Messages.get_message(
                'payment_review_item', 
                lang, 
                id=payment['id'], 
                unit=payment['unit'], 
                amount=payment['amount'] / 100, # Convert satangs back to Baht
                reference=payment['reference']
            )

            # Create the inline keyboard for review actions
            keyboard = [
                [
                    InlineKeyboardButton(Messages.get_message('button_approve', lang), callback_data=f"approve_{payment['id']}"),
                    InlineKeyboardButton(Messages.get_message('button_reject', lang), callback_data=f"reject_{payment['id']}")
                ],
                [
                    InlineKeyboardButton(Messages.get_message('button_view_receipt', lang), callback_data=f"receipt_{payment['id']}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send the message with the action buttons
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    # ==================== CALLBACK HANDLER ====================

    @Permissions.require_operator
    async def handle_payment_callback(self, update: Update, context: CallbackContext) -> None:
        """Processes the inline button press (approve, reject, receipt) from pending_payments."""
        query = update.callback_query
        # Always answer the query to dismiss the loading icon on the user's side
        await query.answer() 
        
        user_id = query.from_user.id
        staff_name = query.from_user.first_name
        lang = self.get_user_language(user_id)
        
        action, payment_id_str = query.data.split('_')
        payment_id = int(payment_id_str)

        payment = db.get_payment_details(payment_id) 

        if not payment:
            await query.edit_message_text(Messages.get_message('payment_not_found', lang))
            return

        # Check if already processed
        if payment['status'] != 'pending':
            status = payment['status']
            await query.edit_message_text(Messages.get_message('already_processed', lang, unit=payment['unit'], status=status))
            return

        # Handle 'receipt' button
        if action == 'receipt':
            receipt_filename = payment.get('receipt_filename')
            
            if not receipt_filename:
                # If there's no receipt_filename, it's a data error
                await query.edit_message_text(Messages.get_message('no_receipt_file', lang))
                return

            try:
                # Construct the full path to the saved receipt file
                file_path = os.path.join(Config.UPLOAD_FOLDER, receipt_filename)
                
                # Send the photo
                with open(file_path, 'rb') as photo_file:
                    caption = Messages.get_message('receipt_caption', lang, id=payment_id, unit=payment['unit'])
                    await context.bot.send_photo(
                        chat_id=user_id, # Send to the staff member's private chat
                        photo=InputFile(photo_file),
                        caption=caption,
                        parse_mode='Markdown'
                    )
                # Re-send the original review message (without changing the text)
                await query.edit_message_reply_markup(query.message.reply_markup) 

            except Exception as e:
                logger.error(f"Error sending receipt photo for ID {payment_id}: {e}")
                await query.edit_message_text(Messages.get_message('receipt_send_error', lang))

        # Handle 'approve' and 'reject' actions
        elif action in ['approve', 'reject']:
            new_status = 'verified' if action == 'approve' else 'rejected'
            
            # 1. Update the database record
            db.update_payment_status(payment_id, new_status, staff_name)
            
            # 2. Get the resident's data for notification
            resident = db.get_resident_by_unit(payment['unit'])
            if resident and resident['telegram_id']:
                # Amount is stored in satangs, convert to Baht for display
                amount_baht = payment['amount'] / 100 
                new_balance_baht = resident['current_balance'] / 100

                # 3. Notify the resident
                notification_key = f'payment_{new_status}_resident_notify'
                resident_lang = resident.get('language', 'en')
                
                await context.bot.send_message(
                    chat_id=resident['telegram_id'],
                    text=Messages.get_message(
                        notification_key,
                        resident_lang,
                        unit=payment['unit'],
                        amount=amount_baht,
                        new_balance=new_balance_baht
                    ),
                    parse_mode='Markdown'
                )

            # 4. Acknowledge and update the review message in the staff chat
            confirmation_key = f'payment_{new_status}_confirmation'
            confirmation_message = Messages.get_message(
                confirmation_key, 
                lang, 
                id=payment_id, 
                unit=payment['unit'], 
                staff=staff_name
            )
            
            await query.edit_message_text(confirmation_message, parse_mode='Markdown')
            
    # ==================== ADMIN & OTHER STAFF COMMAND STUBS ====================
    # NOTE: The 'dashboard' function above replaces the old 'admin_dashboard' stub.
    
    @Permissions.require_admin
    async def broadcast_announcement(self, update: Update, context: CallbackContext) -> None:
        """Handles the /broadcast command (Admin only stub)."""
        lang = self.get_user_language(update.effective_user.id)
        await update.message.reply_text("Broadcast command stub. Functionality not yet implemented.")

    @Permissions.require_admin
    async def payment_reminder(self, update: Update, context: CallbackContext) -> None:
        """Handles the /remind command (Admin only stub)."""
        lang = self.get_user_language(update.effective_user.id)
        await update.message.reply_text("Payment reminder command stub. Functionality not yet implemented.")
        
    @Permissions.require_operator
    async def reply_to_resident(self, update: Update, context: CallbackContext) -> None:
        """Handles the /reply command for staff (Operator only stub)."""
        user_id = update.effective_user.id
        lang = self.get_user_language(user_id)
        
        # 1. Ensure this command is used in the STAFF_LOG_CHAT_ID group
        if update.effective_chat.id != Config.STAFF_LOG_CHAT_ID:
            logger.warning(f"Staff {user_id} attempted /reply outside log chat.")
            return

        # 2. Parse the arguments: Expected format is [user_id] [message...]
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(Messages.get_message('reply_usage_error', lang), parse_mode='Markdown')
            return

        # 3. Extract the target resident's Telegram ID
        try:
            target_id = int(args[0])
            staff_response = " ".join(args[1:])
        except ValueError:
            await update.message.reply_text(Messages.get_message('invalid_resident_id', lang))
            return

        # 4. Find the responding staff member's name
        staff_name = update.effective_user.first_name
        
        # 5. Send the reply to the Resident
        try:
            full_response = Messages.get_message('staff_reply_format', lang, staff=staff_name, response=staff_response)
            
            await context.bot.send_message(
                chat_id=target_id,
                text=full_response,
                parse_mode='Markdown'
            )
            
            # 6. Confirm success in the Staff Log Group
            await update.message.reply_text(Messages.get_message('reply_success', lang, target_id=target_id), parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Failed to send reply to resident {target_id}: {e}")
            await update.message.reply_text(Messages.get_message('reply_send_error', lang, target_id=target_id))
