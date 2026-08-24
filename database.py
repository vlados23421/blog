import sqlite3
import random
import string

class Database:
    def __init__(self, db_path="referral.db"):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                referral_code TEXT UNIQUE,
                referrer_id INTEGER,
                referral_count INTEGER DEFAULT 0,
                bonus_balance INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                bonus_amount INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_name TEXT,
                channel_link TEXT,
                category TEXT,
                subscribers INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
    
    def generate_referral_code(self, length=8):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(chars, k=length))
            self.cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (code,))
            if not self.cursor.fetchone():
                return code
    
    def add_user(self, user_id, username, first_name, referrer_code=None, bonus=10):
        self.cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if self.cursor.fetchone():
            return False
        
        referral_code = self.generate_referral_code()
        
        referrer_id = None
        if referrer_code:
            self.cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (referrer_code,))
            result = self.cursor.fetchone()
            if result:
                referrer_id = result[0]
        
        self.cursor.execute("""
            INSERT INTO users (user_id, username, first_name, referral_code, referrer_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, first_name, referral_code, referrer_id))
        self.conn.commit()
        
        if referrer_id:
            self.cursor.execute("""
                INSERT INTO referrals (referrer_id, referred_id, bonus_amount)
                VALUES (?, ?, ?)
            """, (referrer_id, user_id, bonus))
            self.cursor.execute("""
                UPDATE users SET referral_count = referral_count + 1,
                bonus_balance = bonus_balance + ?
                WHERE user_id = ?
            """, (bonus, referrer_id))
            self.conn.commit()
        
        return True
    
    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()
    
    def get_user_by_code(self, code):
        self.cursor.execute("SELECT * FROM users WHERE referral_code = ?", (code,))
        return self.cursor.fetchone()
    
    def get_referrals(self, user_id):
        self.cursor.execute("""
            SELECT u.user_id, u.username, r.created_at
            FROM referrals r
            JOIN users u ON r.referred_id = u.user_id
            WHERE r.referrer_id = ?
            ORDER BY r.created_at DESC
        """, (user_id,))
        return self.cursor.fetchall()
    
    def get_referral_count(self, user_id):
        self.cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0
    
    def get_leaderboard(self, limit=10):
        self.cursor.execute("""
            SELECT user_id, username, referral_count, bonus_balance
            FROM users
            WHERE referral_count > 0
            ORDER BY referral_count DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()
    
    def add_channel(self, user_id, channel_name, channel_link, category, subscribers=0):
        self.cursor.execute("""
            INSERT INTO channels (user_id, channel_name, channel_link, category, subscribers)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, channel_name, channel_link, category, subscribers))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_user_channels(self, user_id):
        self.cursor.execute("SELECT * FROM channels WHERE user_id = ?", (user_id,))
        return self.cursor.fetchall()
    
    def get_channels_by_category(self, category):
        self.cursor.execute("SELECT * FROM channels WHERE category = ?", (category,))
        return self.cursor.fetchall()
    
    def get_stats(self):
        self.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute("SELECT COUNT(*) FROM referrals")
        total_referrals = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute("SELECT COUNT(*) FROM channels")
        total_channels = self.cursor.fetchone()[0] or 0
        
        return {
            "total_users": total_users,
            "total_referrals": total_referrals,
            "total_channels": total_channels
        }
    
    def close(self):
        self.conn.close()

db = Database()
