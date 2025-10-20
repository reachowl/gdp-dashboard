import sqlite3
import datetime
import os
import sys

# Add the parent directory of this script to the path to import config and database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import from the local directory structure
try:
    from config import Config
    from database import Database
    print("Database and Config modules imported successfully.")
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure config.py and database.py are in the correct directory.")
    sys.exit(1)

# Initialize the database
db = Database()

def setup_test_data():
    """Wipes existing test data and inserts fresh records for testing."""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    print("\n--- Cleaning up existing test data ---")
    # Delete all residents (for a clean start, ONLY recommended for test DBs!)
    cursor.execute("DELETE FROM residents")
    # Delete all payments
    cursor.execute("DELETE FROM payments")
    
    # Reset sequence counters
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='residents'")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='payments'")
    conn.commit()
    print("Clean up successful.")

    # --- 1. Master List Insertion ---
    
    # Resident A: UNREGISTERED (Will test the /register flow)
    # The 'telegram_id' is null here. Replace 1234567890 with your actual Telegram ID to test the registration flow.
    # You must obtain your own ID by talking to @userinfobot on Telegram.
    test_resident_a_id = 1234567890 # <<<<< REPLACE with YOUR Telegram ID for Resident A (the one you'll register)
    
    # Resident B: REGISTERED (Will test /status and /payment flow immediately)
    # Replace 9876543210 with a secondary testing ID, or your staff ID temporarily
    test_resident_b_id = 9876543210 # <<<<< REPLACE with a different Telegram ID for Resident B
    test_staff_id = Config.ADMIN_IDS[0] if Config.ADMIN_IDS else 1043055001 # Your main staff ID
    
    # We will use the staff ID for Resident B's data to simplify testing /status
    
    residents_data = [
        # Resident A: UNREGISTERED (will use the /register command)
        ('88/01', 'Test User A', '1043055001', None, None, -5000000, 'en'), # 50000.00 Baht owed
        # Resident B: PRE-REGISTERED (for immediate /status and /payment testing)
        ('88/02', 'Test User B', '8118541961', test_staff_id, 'Staff Tester', -120000, 'th'), # 1200.00 Baht owed
    ]

    print("\n--- Inserting Test Residents ---")
    for unit, owner_name, phone, telegram_id, telegram_name, balance, lang in residents_data:
        try:
            cursor.execute('''
                INSERT INTO residents (unit, owner_name, phone, telegram_id, telegram_name, current_balance, language)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (unit, owner_name, phone, telegram_id, telegram_name, balance, lang))
            print(f"✅ Inserted resident: {unit}")
        except sqlite3.IntegrityError:
            print(f"❌ Unit {unit} already exists (skipping).")
            
    conn.commit()

    # --- 2. Pending Payment Insertion ---
    
    # Insert a dummy payment to test the staff /pending command right away
    print("\n--- Inserting Pending Payment (for Staff /pending test) ---")
    try:
        # Assuming Resident B made a payment of 1000.50 Baht (100050 satang)
        cursor.execute('''
            INSERT INTO payments (unit, amount, reference, receipt_filename, telegram_user_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('88/02', 100050, 'Payment for June/2025', 'AgACAgIA...', test_staff_id, 'pending'))
        
        print("✅ Inserted one pending payment for Unit 88/02.")
    except Exception as e:
        print(f"❌ Failed to insert pending payment: {e}")
        
    conn.commit()
    conn.close()
    
    print("\n--- Test Data Setup Complete ---")
    print(f"To test: ")
    print(f"1. **Resident Flow:** Start the bot with ID `{test_resident_a_id}` and use `/register 88/01` (PIN 1234).")
    print(f"2. **Staff Flow:** Start the bot with ID `{test_staff_id}` and use `/pending`.")

if __name__ == '__main__':
    setup_test_data()
