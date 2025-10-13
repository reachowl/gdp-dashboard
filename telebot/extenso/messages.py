# messages.py

class Messages:
    @staticmethod
    def get_message(key, language='en', **kwargs):
        """
        Retrieves a message based on a key and language, substituting placeholders.
        
        Args:
            key (str): The message key (e.g., 'welcome').
            language (str): The desired language ('en' or 'th').
            **kwargs: Variables to replace in the message (e.g., unit='88/01', amount=50000).
        """
        messages = {
            # ==================== SYSTEM MESSAGES ====================
            'welcome': {
                'en': "🏠 **Welcome to Extenso Village!**\n\nI'm your assistant for maintenance fees and village communications. Please choose your language to continue.",
                'th': "🏠 **ยินดีต้อนรับสู่ เอ็กเทนโซ วิลเลจ!**\n\nฉันเป็นผู้ช่วยสำหรับค่าบำรุงรักษาและการสื่อสารในหมู่บ้าน กรุณาเลือกภาษาของคุณเพื่อดำเนินการต่อ"
            },
            'welcome_admin': {
                'en': "👑 **Admin Dashboard** - Use /dashboard.",
                'th': "👑 **แดชบอร์ดผู้ดูแล** - ใช้ /dashboard."
            },
            'welcome_operator': {
                'en': "🎯 **Operator Dashboard** - Use /dashboard or /pending.",
                'th': "🎯 **แดชบอร์ดผู้ปฏิบัติงาน** - ใช้ /dashboard หรือ /pending."
            },
            'language_set': {
                'en': "✅ Language set to English",
                'th': "✅ ตั้งค่าภาษาเป็นไทยแล้ว"
            },
            'help_text': {
                'en': (
                    "**Available Commands**:\n"
                    "/start - Main menu\n"
                    "/register - Register your unit\n"
                    "/payment - Report a payment\n"
                    "/cancel - Cancel any ongoing action\n"
                    "\nIf you send a text message outside of a command, it will be forwarded to staff as a **support request**."
                ),
                'th': (
                    "**คำสั่งที่ใช้ได้**:\n"
                    "/start - เมนูหลัก\n"
                    "/register - ลงทะเบียนบ้านของคุณ\n"
                    "/payment - แจ้งชำระเงิน\n"
                    "/cancel - ยกเลิกการดำเนินการที่กำลังทำอยู่\n"
                    "\nหากคุณส่งข้อความที่ไม่ใช่คำสั่ง ข้อความนั้นจะถูกส่งไปยังเจ้าหน้าที่เพื่อเป็น**คำขอความช่วยเหลือ**"
                )
            },
            'conversation_cancelled': {
                'en': "🛑 Action cancelled. You can start a new command now.",
                'th': "🛑 ยกเลิกการดำเนินการแล้ว คุณสามารถเริ่มคำสั่งใหม่ได้"
            },
            
            # ==================== REGISTRATION ====================
            'register_prompt': {
                'en': "🔐 **Registration**\n\nTo access all features, please register your unit:\n\nUsage: `/register UNIT_NUMBER`\nExample: `/register 88/01`\n\n*Or, just type your UNIT_NUMBER now to proceed.*",
                'th': "🔐 **การลงทะเบียน**\n\nเพื่อเข้าถึงฟีเจอร์ทั้งหมด กรุณาลงทะเบียนบ้านของคุณ:\n\nตัวอย่าง: `/register 88/01`\n\n*หรือพิมพ์หมายเลขบ้านของคุณตอนนี้เพื่อดำเนินการต่อ*"
            },
            'pin_prompt': {
                'en': "🔑 Unit **{unit}** found. For security, please enter your PIN (Last 4 digits of your phone number or the last part of your unit, e.g., '01' for 88/01).",
                'th': "🔑 พบหมายเลขบ้าน **{unit}** เพื่อความปลอดภัย กรุณาป้อน PIN ของคุณ (4 ตัวท้ายของเบอร์โทรศัพท์ หรือส่วนท้ายของหมายเลขบ้าน เช่น '01' สำหรับ 88/01)"
            },
            'registration_success': {
                'en': "🎉 **Registration successful!** Welcome to Extenso Village, Unit **{unit}**.",
                'th': "🎉 **ลงทะเบียนสำเร็จ!** ยินดีต้อนรับสู่ เอ็กเทนโซ วิลเลจ บ้านเลขที่ **{unit}**"
            },
            'already_registered': {
                'en': "ℹ️ You are already registered to Unit **{unit}**.",
                'th': "ℹ️ คุณได้ลงทะเบียนบ้านเลขที่ **{unit}** ไว้แล้ว"
            },

            # ==================== MAIN MENU/STATUS ====================
            'main_menu_resident': {
                'en': "👋 Hello, **{user_name}**!\n\nUnit: **{unit}**\n{balance_text}",
                'th': "👋 สวัสดี, **{user_name}**!\n\nบ้านเลขที่: **{unit}**\n{balance_text}"
            },
            'current_balance': {
                'en': "Current Balance: **฿ {balance:,}**",
                'th': "ยอดคงเหลือปัจจุบัน: **฿ {balance:,}**"
            },
            'menu_check_balance': {
                'en': "Check Balance",
                'th': "ตรวจสอบยอดเงิน"
            },
            'menu_report_payment': {
                'en': "Report Payment / Deposit",
                'th': "แจ้งชำระเงิน / เงินมัดจำ"
            },
            
            # ==================== PAYMENT ====================
            'payment_prompt_receipt': {
                'en': "📸 Please upload a photo of your **payment receipt** now.",
                'th': "📸 กรุณาอัปโหลดรูปภาพ**ใบเสร็จรับเงิน**ของคุณตอนนี้"
            },
            'payment_prompt_details': {
                'en': "📝 Please provide the **payment details** (Amount and Reference/Description, e.g., '50,000 for maintenance fee').",
                'th': "📝 กรุณาให้**รายละเอียดการชำระเงิน** (จำนวนเงินและรายละเอียด/คำอธิบาย เช่น '50,000 สำหรับค่าบำรุงรักษา')"
            },
            'payment_report_success': {
                'en': "✅ Payment ID: **{payment_id}** (฿ {amount:,}) successfully reported. Staff will verify it shortly. You will be notified of the result.",
                'th': "✅ แจ้งชำระเงิน ID: **{payment_id}** (฿ {amount:,}) สำเร็จ เจ้าหน้าที่จะตรวจสอบในไม่ช้า คุณจะได้รับการแจ้งเตือนผลการตรวจสอบ"
            },
            'payment_verified_resident': {
                'en': "✅ Your payment ID **{payment_id}** (฿ {amount:,}) for Unit **{unit}** has been **VERIFIED** by {staff_name}. Your balance has been updated.",
                'th': "✅ การชำระเงิน ID **{payment_id}** (฿ {amount:,}) สำหรับบ้านเลขที่ **{unit}** ได้รับการ**ยืนยัน**โดย {staff_name} ยอดเงินของคุณได้รับการอัปเดตแล้ว"
            },
            'payment_rejected_resident': {
                'en': "❌ Your payment ID **{payment_id}** (฿ {amount:,}) for Unit **{unit}** was **REJECTED** by {staff_name}. Please report it again with a clear receipt.",
                'th': "❌ การชำระเงิน ID **{payment_id}** (฿ {amount:,}) สำหรับบ้านเลขที่ **{unit}** ถูก**ปฏิเสธ**โดย {staff_name} กรุณาแจ้งใหม่พร้อมใบเสร็จที่ชัดเจน"
            },
            
            # ==================== STAFF/LOG ====================
            'staff_payment_notification': {
                'en': (
                    "🚨 **NEW PAYMENT PENDING** 🚨\n\n"
                    "ID: `{payment_id}`\n"
                    "Unit: **{unit}**\n"
                    "Resident: {resident_name} (ID: `{telegram_user_id}`)\n"
                    "Amount: **฿ {amount:,}**\n"
                    "Reference: {reference}\n\n"
                    "Please verify the receipt and take action."
                ),
                'th': (
                    "🚨 **มีการชำระเงินใหม่ที่รอดำเนินการ** 🚨\n\n"
                    "ID: `{payment_id}`\n"
                    "บ้านเลขที่: **{unit}**\n"
                    "ผู้อยู่อาศัย: {resident_name} (ID: `{telegram_user_id}`)\n"
                    "จำนวนเงิน: **฿ {amount:,}**\n"
                    "รายละเอียด: {reference}\n\n"
                    "กรุณาตรวจสอบใบเสร็จและดำเนินการ"
                )
            },
            'staff_payment_verified_log': {
                'en': "✅ Payment ID **{payment_id}** verified by **{staff_name}**.",
                'th': "✅ ยืนยันการชำระเงิน ID **{payment_id}** โดย **{staff_name}** แล้ว"
            },
            'staff_payment_rejected_log': {
                'en': "❌ Payment ID **{payment_id}** rejected by **{staff_name}**.",
                'th': "❌ ปฏิเสธการชำระเงิน ID **{payment_id}** โดย **{staff_name}** แล้ว"
            },
            'staff_payment_already_processed': {
                'en': "⚠️ Payment ID **{payment_id}** has already been processed as **{status}**.",
                'th': "⚠️ การชำระเงิน ID **{payment_id}** ได้รับการดำเนินการแล้วในสถานะ **{status}**"
            },
            'staff_pending_payments': {
                'en': "🧾 **Pending Payments ({count})**:\n\n{payments_list}",
                'th': "🧾 **การชำระเงินที่รอดำเนินการ ({count})**:\n\n{payments_list}"
            },
            'staff_support_log_message': {
                'en': (
                    "💬 **NEW RESIDENT MESSAGE** 💬\n\n"
                    "Unit: **{unit}**\n"
                    "Resident: {resident_name} (ID: `{resident_id}`)\n"
                    "Message: *{message}*\n\n"
                    "Reply using: `/reply {resident_id} [Your Message]`"
                ),
                'th': "💬 **ข้อความใหม่จากผู้อยู่อาศัย** 💬\n\n"
                    "บ้านเลขที่: **{unit}**\n"
                    "ผู้อยู่อาศัย: {resident_name} (ID: `{resident_id}`)\n"
                    "ข้อความ: *{message}*\n\n"
                    "ตอบกลับด้วย: `/reply {resident_id} [ข้อความของคุณ]`"
            },
            'support_message_received': {
                'en': "✅ Your message has been sent to the staff. They will reply to you here shortly.",
                'th': "✅ ข้อความของคุณถูกส่งไปยังเจ้าหน้าที่แล้ว พวกเขาจะตอบกลับคุณที่นี่ในไม่ช้า"
            },
            'support_message_failed': {
                'en': "⚠️ Failed to send your message to staff. Please try again later.",
                'th': "⚠️ ไม่สามารถส่งข้อความของคุณไปยังเจ้าหน้าที่ได้ โปรดลองอีกครั้งในภายหลัง"
            },
            'staff_resident_info': {
                'en': "👤 Resident: {resident_name} (Unit: {unit}, ID: `{telegram_id}`). Current Balance: ฿{balance:,}. Last Payment: {last_payment} ({days_since} days ago)",
                'th': "👤 ผู้อยู่อาศัย: {resident_name} (บ้านเลขที่: {unit}, ID: `{telegram_id}`). ยอดคงเหลือปัจจุบัน: ฿{balance:,}. ชำระล่าสุด: {last_payment} (เมื่อ {days_since} วันที่แล้ว)"
            },
            'staff_resident_count': {
                'en': "Total registered residents: {count}",
                'th': "จำนวนผู้อยู่อาศัยที่ลงทะเบียน: {count} ราย"
            },
            
            # ==================== ERROR/ACCESS ====================
            'not_registered': {
                'en': "❌ Please register first using /register",
                'th': "❌ กรุณาลงทะเบียนด้วย /register ก่อน"
            },
            'unit_not_found': {
                'en': "❌ Unit {unit} not found in the system.",
                'th': "❌ ไม่พบหน่วย {unit} ในระบบ"
            },
            'pin_incorrect': {
                'en': "❌ Incorrect PIN. Please try again or type /cancel to restart.",
                'th': "❌ PIN ไม่ถูกต้อง กรุณาลองอีกครั้ง หรือพิมพ์ /cancel เพื่อเริ่มต้นใหม่"
            },
            'staff_access_required': {
                'en': "❌ Operator access required",
                'th': "❌ ต้องการการเข้าถึงผู้ปฏิบัติงาน"
            },
            'admin_access_required': {
                'en': "❌ Administrator access required", 
                'th': "❌ ต้องการการเข้าถึงผู้ดูแลระบบ"
            }
        }
        
        # 1. Get the base message for the language
        try:
            message = messages[key][language]
        except KeyError:
            # Fallback to English if the key/language is missing
            message = messages.get(key, {}).get('en', f"Error: Message key '{key}' not found.")

        # 2. Replace variables in the message
        for k, value in kwargs.items():
            formatted_value = str(value)
            
            # Handle comma formatting for numbers (e.g., amount=50000 becomes 50,000.00)
            if k.endswith(':,') and isinstance(value, (int, float)):
                # Store amount in the DB as integer (satang/cents) but display as currency (divided by 100)
                display_value = value / 100 if value >= 100 else value 
                formatted_value = f"{display_value:,.2f}"
                k = k.rstrip(':,')
                message = message.replace(f"{{{k}:,}}", formatted_value)
            
            # Regular replacement for strings or numbers without special formatting
            message = message.replace(f"{{{k}}}", str(value))
        
        return message
