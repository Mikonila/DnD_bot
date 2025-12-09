import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
import os


class Database:
    def __init__(self, db_name: str = "dnd_bot.db"):
        self.db_name = db_name
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Таблица для ваншотов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oneshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date_time TEXT NOT NULL,
                story TEXT,
                location TEXT,
                price TEXT,
                free_drink BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица для кампаний
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date_time TEXT NOT NULL,
                duration TEXT,
                story TEXT,
                location TEXT,
                price TEXT,
                free_drink BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица для регистраций на ваншоты
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oneshot_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                oneshot_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (oneshot_id) REFERENCES oneshots(id) ON DELETE CASCADE,
                UNIQUE(oneshot_id, user_id)
            )
        """)

        # Таблица для регистраций на кампании
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
                UNIQUE(campaign_id, user_id)
            )
        """)

        # Таблица для уведомлений о новых мероприятиях
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                notified_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_type)
            )
        """)

        # Таблица для отслеживания отправленных напоминаний
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reminder_type TEXT NOT NULL,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(event_type, event_id, user_id, reminder_type)
            )
        """)

        # Таблица для отзывов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                text TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def add_oneshot(self, name: str, date_time: str, story: str, location: str, price: str, free_drink: bool) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO oneshots (name, date_time, story, location, price, free_drink)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, date_time, story, location, price, 1 if free_drink else 0))
        oneshot_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return oneshot_id

    def add_campaign(self, name: str, date_time: str, duration: str, story: str, location: str, price: str, free_drink: bool) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO campaigns (name, date_time, duration, story, location, price, free_drink)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, date_time, duration, story, location, price, 1 if free_drink else 0))
        campaign_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return campaign_id

    def get_upcoming_oneshots(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM oneshots 
            WHERE datetime(date_time) > datetime('now')
            ORDER BY datetime(date_time) ASC
        """)
        columns = [description[0] for description in cursor.description]
        oneshots = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return oneshots

    def get_upcoming_campaigns(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM campaigns 
            WHERE datetime(date_time) > datetime('now')
            ORDER BY datetime(date_time) ASC
        """)
        columns = [description[0] for description in cursor.description]
        campaigns = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return campaigns

    def register_for_oneshot(self, oneshot_id: int, user_id: int, username: str = None, first_name: str = None) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO oneshot_registrations (oneshot_id, user_id, username, first_name)
                VALUES (?, ?, ?, ?)
            """, (oneshot_id, user_id, username, first_name))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def register_for_campaign(self, campaign_id: int, user_id: int, username: str = None, first_name: str = None) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO campaign_registrations (campaign_id, user_id, username, first_name)
                VALUES (?, ?, ?, ?)
            """, (campaign_id, user_id, username, first_name))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def get_oneshot_by_id(self, oneshot_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM oneshots WHERE id = ?", (oneshot_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        return None

    def get_campaign_by_id(self, campaign_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        return None

    def get_registered_users_for_oneshot(self, oneshot_id: int) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM oneshot_registrations WHERE oneshot_id = ?", (oneshot_id,))
        columns = [description[0] for description in cursor.description]
        registrations = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return registrations

    def get_registered_users_for_campaign(self, campaign_id: int) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM campaign_registrations WHERE campaign_id = ?", (campaign_id,))
        columns = [description[0] for description in cursor.description]
        registrations = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return registrations

    def add_notification_request(self, user_id: int, event_type: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO notifications (user_id, event_type)
            VALUES (?, ?)
        """, (user_id, event_type))
        conn.commit()
        conn.close()

    def get_users_to_notify(self, event_type: str) -> List[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM notifications WHERE event_type = ?", (event_type,))
        user_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return user_ids

    def get_all_registrations_for_reminders(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получаем все регистрации на ваншоты
        cursor.execute("""
            SELECT 'oneshot' as event_type, o.id as event_id, r.user_id, o.date_time, o.name
            FROM oneshot_registrations r
            JOIN oneshots o ON r.oneshot_id = o.id
            WHERE datetime(o.date_time) > datetime('now')
        """)
        
        oneshot_reminders = []
        for row in cursor.fetchall():
            oneshot_reminders.append({
                'event_type': row[0],
                'event_id': row[1],
                'user_id': row[2],
                'date_time': row[3],
                'name': row[4]
            })
        
        # Получаем все регистрации на кампании
        cursor.execute("""
            SELECT 'campaign' as event_type, c.id as event_id, r.user_id, c.date_time, c.name
            FROM campaign_registrations r
            JOIN campaigns c ON r.campaign_id = c.id
            WHERE datetime(c.date_time) > datetime('now')
        """)
        
        campaign_reminders = []
        for row in cursor.fetchall():
            campaign_reminders.append({
                'event_type': row[0],
                'event_id': row[1],
                'user_id': row[2],
                'date_time': row[3],
                'name': row[4]
            })
        
        conn.close()
        return oneshot_reminders + campaign_reminders


    def get_all_registrations(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()

        registrations: List[Dict[str, Any]] = []

        # Ваншоты
        cursor.execute("""
            SELECT
                'oneshot' AS event_type,
                o.name AS event_name,
                o.date_time AS date_time,
                r.user_id AS user_id,
                r.username AS username,
                r.first_name AS first_name,
                r.registered_at AS registered_at
            FROM oneshot_registrations r
            JOIN oneshots o ON r.oneshot_id = o.id
            ORDER BY datetime(o.date_time) ASC, datetime(r.registered_at) ASC
        """)
        for row in cursor.fetchall():
            registrations.append({
                "event_type": row[0],
                "event_name": row[1],
                "date_time": row[2],
                "user_id": row[3],
                "username": row[4],
                "first_name": row[5],
                "registered_at": row[6],
            })

        # Кампании
        cursor.execute("""
            SELECT
                'campaign' AS event_type,
                c.name AS event_name,
                c.date_time AS date_time,
                r.user_id AS user_id,
                r.username AS username,
                r.first_name AS first_name,
                r.registered_at AS registered_at
            FROM campaign_registrations r
            JOIN campaigns c ON r.campaign_id = c.id
            ORDER BY datetime(c.date_time) ASC, datetime(r.registered_at) ASC
        """)
        for row in cursor.fetchall():
            registrations.append({
                "event_type": row[0],
                "event_name": row[1],
                "date_time": row[2],
                "user_id": row[3],
                "username": row[4],
                "first_name": row[5],
                "registered_at": row[6],
            })

        conn.close()
        return registrations

    def mark_reminder_sent(self, event_type: str, event_id: int, user_id: int, reminder_type: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO reminders (event_type, event_id, user_id, reminder_type)
            VALUES (?, ?, ?, ?)
        """, (event_type, event_id, user_id, reminder_type))
        conn.commit()
        conn.close()

    def was_reminder_sent(self, event_type: str, event_id: int, user_id: int, reminder_type: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM reminders
            WHERE event_type = ? AND event_id = ? AND user_id = ? AND reminder_type = ?
        """, (event_type, event_id, user_id, reminder_type))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def delete_oneshot(self, oneshot_id: int) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM oneshots WHERE id = ?", (oneshot_id,))
        conn.commit()
        conn.close()

    def delete_campaign(self, campaign_id: int) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        conn.commit()
        conn.close()

    def add_review(self, user_id: int, username: str, first_name: str, text: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reviews (user_id, username, first_name, text)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, text))
        conn.commit()
        conn.close()

    def get_latest_reviews(self, limit: int = 5):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, first_name, text, created_at FROM reviews
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        reviews = cursor.fetchall()
        conn.close()
        return reviews

    def get_all_reviews(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, first_name, text, created_at FROM reviews
            ORDER BY created_at DESC
        """)
        reviews = cursor.fetchall()
        conn.close()
        return reviews

    def delete_review(self, review_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        conn.commit()
        conn.close()
