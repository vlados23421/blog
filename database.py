import sqlite3
import random
import string
from datetime import datetime, timedelta

class Database:
    def __init__(self, db_path="referral.db"):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        # Таблица пользователей
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                referral_code TEXT UNIQUE,
                referrer_id INTEGER,
                referral_count INTEGER DEFAULT 0,
                bonus_balance INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                premium_until TEXT,
                is_blocked INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_active TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица рефералов
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                bonus_amount INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица каналов
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_name TEXT,
                channel_link TEXT,
                category TEXT,
                subscribers INTEGER DEFAULT 0,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица избранного
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER,
                channel_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, channel_id)
            )
        """)
        
        # Таблица партнёрств
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS partnerships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel1_id INTEGER,
                channel2_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица отзывов
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                rating INTEGER,
                comment TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
    
    # ==================== ГЕНЕРАЦИЯ КОДА ====================
    
    def generate_referral_code(self, length=8):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(chars, k=length))
            self.cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (code,))
            if not self.cursor.fetchone():
                return code
    
    # ==================== ПОЛЬЗОВАТЕЛИ ====================
    
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
    
    def get_all_users(self):
        self.cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        return self.cursor.fetchall()
    
    def update_user_activity(self, user_id):
        self.cursor.execute(
            "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()
    
    def get_user_rank(self, user_id):
        self.cursor.execute("""
            SELECT COUNT(*) + 1 FROM users 
            WHERE referral_count > (SELECT referral_count FROM users WHERE user_id = ?)
        """, (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 1
    
    # ==================== БЛОКИРОВКА ====================
    
    def is_user_blocked(self, user_id):
        self.cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        return result and result[0] == 1
    
    def block_user(self, user_id):
        self.cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
        self.conn.commit()
    
    def unblock_user(self, user_id):
        self.cursor.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,))
        self.conn.commit()
    
    # ==================== РЕФЕРАЛЫ ====================
    
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
    
    # ==================== ПРЕМИУМ ====================
    
    def set_premium(self, user_id, months):
        until = (datetime.now() + timedelta(days=months*30)).isoformat()
        self.cursor.execute(
            "UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?",
            (until, user_id)
        )
        self.conn.commit()
    
    def is_premium(self, user_id):
        self.cursor.execute(
            "SELECT is_premium, premium_until FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = self.cursor.fetchone()
        if not result:
            return False
        if result[0] == 1 and result[1] and datetime.now().isoformat() < result[1]:
            return True
        return False
    
    # ==================== КАНАЛЫ ====================
    
    def add_channel(self, user_id, channel_name, channel_link, category, subscribers, description=""):
        self.cursor.execute("""
            INSERT INTO channels (user_id, channel_name, channel_link, category, subscribers, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, channel_name, channel_link, category, subscribers, description))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_channel_by_id(self, channel_id):
        self.cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
        return self.cursor.fetchone()
    
    def get_user_channels(self, user_id):
        self.cursor.execute(
            "SELECT * FROM channels WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC",
            (user_id,)
        )
        return self.cursor.fetchall()
    
    def get_channels_by_category(self, category):
        self.cursor.execute(
            "SELECT * FROM channels WHERE category = ? AND is_active = 1 ORDER BY subscribers DESC",
            (category,)
        )
        return self.cursor.fetchall()
    
    def get_all_channels(self):
        self.cursor.execute("SELECT * FROM channels WHERE is_active = 1 ORDER BY created_at DESC")
        return self.cursor.fetchall()
    
    def update_channel(self, channel_id, name=None, category=None, subscribers=None, description=None):
        if name:
            self.cursor.execute("UPDATE channels SET channel_name = ? WHERE id = ?", (name, channel_id))
        if category:
            self.cursor.execute("UPDATE channels SET category = ? WHERE id = ?", (category, channel_id))
        if subscribers is not None:
            self.cursor.execute("UPDATE channels SET subscribers = ? WHERE id = ?", (subscribers, channel_id))
        if description is not None:
            self.cursor.execute("UPDATE channels SET description = ? WHERE id = ?", (description, channel_id))
        self.cursor.execute(
            "UPDATE channels SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (channel_id,)
        )
        self.conn.commit()
    
    def delete_channel(self, channel_id):
        self.cursor.execute("UPDATE channels SET is_active = 0 WHERE id = ?", (channel_id,))
        self.conn.commit()
    
    # ==================== ИЗБРАННОЕ ====================
    
    def add_favorite(self, user_id, channel_id):
        try:
            self.cursor.execute(
                "INSERT OR IGNORE INTO favorites (user_id, channel_id) VALUES (?, ?)",
                (user_id, channel_id)
            )
            self.conn.commit()
            return True
        except:
            return False
    
    def remove_favorite(self, user_id, channel_id):
        self.cursor.execute(
            "DELETE FROM favorites WHERE user_id = ? AND channel_id = ?",
            (user_id, channel_id)
        )
        self.conn.commit()
    
    def get_favorites(self, user_id):
        self.cursor.execute("""
            SELECT c.* FROM favorites f
            JOIN channels c ON f.channel_id = c.id
            WHERE f.user_id = ? AND c.is_active = 1
        """, (user_id,))
        return self.cursor.fetchall()
    
    def is_favorite(self, user_id, channel_id):
        self.cursor.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND channel_id = ?",
            (user_id, channel_id)
        )
        return self.cursor.fetchone() is not None
    
    # ==================== ПАРТНЁРСТВА ====================
    
    def add_partnership(self, channel1_id, channel2_id):
        self.cursor.execute("""
            INSERT INTO partnerships (channel1_id, channel2_id, status)
            VALUES (?, ?, 'pending')
        """, (channel1_id, channel2_id))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_user_partnerships(self, user_id):
        self.cursor.execute("""
            SELECT c1.channel_name, c2.channel_name, p.status, p.created_at
            FROM partnerships p
            JOIN channels c1 ON p.channel1_id = c1.id
            JOIN channels c2 ON p.channel2_id = c2.id
            WHERE (c1.user_id = ? OR c2.user_id = ?) AND p.status = 'active'
        """, (user_id, user_id))
        return self.cursor.fetchall()
    
    def update_partnership_status(self, partnership_id, status):
        self.cursor.execute("""
            UPDATE partnerships SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (status, partnership_id))
        self.conn.commit()
    
    # ==================== ОТЗЫВЫ ====================
    
    def add_review(self, user_id, rating, comment=""):
        self.cursor.execute(
            "INSERT INTO reviews (user_id, rating, comment) VALUES (?, ?, ?)",
            (user_id, rating, comment)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_reviews(self, limit=10):
        self.cursor.execute(
            "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return self.cursor.fetchall()
    
    def get_avg_rating(self):
        self.cursor.execute("SELECT AVG(rating) FROM reviews")
        result = self.cursor.fetchone()
        return round(result[0], 1) if result and result[0] else 0
    
    # ==================== СТАТИСТИКА ====================
    
    def get_stats(self):
        self.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute("SELECT COUNT(*) FROM referrals")
        total_referrals = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute("SELECT COUNT(*) FROM channels WHERE is_active = 1")
        total_channels = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute("SELECT SUM(bonus_balance) FROM users")
        total_bonus = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
        total_premium = self.cursor.fetchone()[0] or 0
        
        return {
            "total_users": total_users,
            "total_referrals": total_referrals,
            "total_channels": total_channels,
            "total_bonus": total_bonus,
            "total_premium": total_premium
        }
    
    def close(self):
        self.conn.close()

db = Database()
