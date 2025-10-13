# database.py

import sqlite3
import datetime
import os
from config import Config

class Database:
    def __init__(self):
        self.db_path = 'extenso_village.db'
        self.init_database()
        
    def get_connection(self):
        # Using check_same_thread=False for flexibility in bot threads
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        os.makedirs(Config.DATA_FOLDER, exist_ok=True)
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Residents table (Master Data)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS residents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit TEXT UNIQUE NOT NULL,
                owner_name TEXT NOT NULL,
                phone TEXT,
                telegram_id INTEGER UNIQUE,
                telegram_name TEXT,
                current_balance INTEGER DEFAULT 0,
                monthly_charge INTEGER DEFAULT 50000,
                last_payment_date TEXT,
                registration_date TEXT,
                language TEXT DEFAULT 'en',
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Payments table (Transaction History)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reference TEXT,
                receipt_filename TEXT NOT NULL,
                telegram_user_id INTEGER NOT NULL,
                language TEXT DEFAULT 'en',
                status TEXT DEFAULT 'pending', -- 'pending', 'verified', 'rejected'
                verified_by INTEGER,
                verification_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Staff Communications Log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS support_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER NOT NULL,
                resident_telegram_id INTEGER NOT NULL,
                log_type TEXT NOT NULL, -- 'RESIDENT_MESSAGE', 'STAFF_REPLY', 'PAYMENT_ACTION'
                content TEXT NOT NULL,
                metadata TEXT, -- JSON string for extra info (e.g., payment ID, staff ID)
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    # --- RESIDENTS CRUD/Utilities ---
        
    def get_resident_by_unit(self, unit):
        """Retrieves a resident by unit number."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM residents WHERE unit = ?', (unit,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def get_resident_by_telegram(self, telegram_id):
        """Retrieves a resident by Telegram ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM residents WHERE telegram_id = ?', (telegram_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    # 🚨 NEW FUNCTION: Retrieve resident balance and info by Telegram ID 🚨
    def get_resident_balance_by_telegram_id(self, telegram_id):
        """
        Retrieves the current_balance, unit, and language for a resident by their telegram_id.
        Returns {'unit': str, 'current_balance': int, 'language': str} or None.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT unit, current_balance, language FROM residents WHERE telegram_id = ?',
            (telegram_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None

    def update_resident_registration(self, unit, telegram_id, telegram_name, language):
        """
        Updates an existing resident's Telegram ID and name after successful registration.
        Also sets the language preference.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Check for existing user with this telegram_id and de-register them first
        # This prevents duplicate registration errors
        cursor.execute('UPDATE residents SET telegram_id = NULL, telegram_name = NULL WHERE telegram_id = ?', (telegram_id,))
        
        # Update the target unit
        cursor.execute('''
            UPDATE residents 
            SET telegram_id = ?, telegram_name = ?, language = ?, registration_date = ?
            WHERE unit = ?
        ''', (telegram_id, telegram_name, language, now, unit))
        
        conn.commit()
        conn.close()
        
        # Check if the update was successful
        return cursor.rowcount > 0

    # --- PAYMENTS CRUD/Utilities ---

    def add_payment(self, unit, amount, reference, receipt_filename, telegram_user_id, language):
        """Adds a new pending payment entry."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Note: 'status' defaults to 'pending' in the table definition
        cursor.execute('''
            INSERT INTO payments (unit, amount, reference, receipt_filename, telegram_user_id, language)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (unit, amount, reference, receipt_filename, telegram_user_id, language))
        
        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return payment_id

    def get_pending_payments(self):
        """Retrieves all payments with status 'pending'."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM payments WHERE status = ? ORDER BY created_at ASC', 
            ('pending',)
        )
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]

    def get_payment_by_id(self, payment_id):
        """Retrieves a single payment record by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, unit, amount, reference, receipt_filename, telegram_user_id, language FROM payments WHERE id = ?', (payment_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def update_payment_status(self, payment_id, status, verified_by):
        """Updates payment status and credits/debits the resident's account."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT unit, amount FROM payments WHERE id = ?', (payment_id,))
        payment = cursor.fetchone()
        if not payment:
            conn.close()
            return False
        
        unit, amount = payment['unit'], payment['amount']
        
        cursor.execute('''
            UPDATE payments 
            SET status = ?, verified_by = ?, verification_date = ?
            WHERE id = ?
        ''', (status, verified_by, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), payment_id))
        
        if status == 'verified':
            # Add amount to current_balance
            cursor.execute('''
                UPDATE residents 
                SET current_balance = current_balance + ?, last_payment_date = ?
                WHERE unit = ?
            ''', (amount, datetime.datetime.now().strftime('%Y-%m-%d'), unit))
        
        conn.commit()
        conn.close()
        
        return True

    # --- SUPPORT LOGGING ---
    
    def log_support_message(self, resident_telegram_id, log_type, content, metadata=None):
        """Logs a message from a resident or a reply from staff."""
        conn = self.get_connection()
        cursor = conn.cursor()

        resident = self.get_resident_by_telegram(resident_telegram_id)
        resident_id = resident['id'] if resident else None
        
        metadata_json = metadata if metadata else '{}'
        
        cursor.execute('''
            INSERT INTO support_log (resident_id, resident_telegram_id, log_type, content, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', (resident_id, resident_telegram_id, log_type, content, metadata_json))
        
        conn.commit()
        conn.close()
        
        return cursor.lastrowid
        
db = Database()
