"""
قاعدة بيانات حفظ الإحصائيات وسجل المباريات (SQLite)
Chess Bot Database Management
"""

import sqlite3
import datetime
from typing import Optional, Dict, Any, List


class ChessDatabase:
    """إدارة بيانات اللاعبين وسجلات المباريات ونظام التصنيف (ELO)"""

    def __init__(self, db_path: str = "chess_bot.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self):
        return self._conn

    def _init_db(self):
        """إنشاء الجداول اللازمة إذا لم تكن موجودة"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    rating INTEGER DEFAULT 1200,
                    wins_vs_ai INTEGER DEFAULT 0,
                    losses_vs_ai INTEGER DEFAULT 0,
                    draws_vs_ai INTEGER DEFAULT 0,
                    wins_vs_pvp INTEGER DEFAULT 0,
                    losses_vs_pvp INTEGER DEFAULT 0,
                    draws_vs_pvp INTEGER DEFAULT 0,
                    created_at TEXT,
                    last_played TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS games_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    white_id INTEGER,
                    white_name TEXT,
                    black_id INTEGER,
                    black_name TEXT,
                    mode TEXT,
                    winner_id INTEGER,
                    result_type TEXT,
                    pgn TEXT,
                    moves_count INTEGER,
                    played_at TEXT
                )
            """)
            conn.commit()

    def get_or_create_user(self, user_id: int, username: str) -> Dict[str, Any]:
        """استرجاع بيانات اللاعب أو تسجيله لأول مرة"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                # تحديث الاسم إذا تغير
                if row["username"] != username:
                    cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
                    conn.commit()
                return dict(row)

            now = datetime.datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO users (user_id, username, rating, created_at, last_played)
                VALUES (?, ?, 1200, ?, ?)
            """, (user_id, username, now, now))
            conn.commit()

            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return dict(cursor.fetchone())

    def update_rating_elo(self, winner_id: Optional[int], loser_id: Optional[int], is_draw: bool = False):
        """تحديث تصنيف ELO للاعبين في طور PvP"""
        if not winner_id or not loser_id:
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rating FROM users WHERE user_id = ?", (winner_id,))
            w_row = cursor.fetchone()
            cursor.execute("SELECT rating FROM users WHERE user_id = ?", (loser_id,))
            l_row = cursor.fetchone()

            if not w_row or not l_row:
                return

            r_w = w_row["rating"]
            r_l = l_row["rating"]

            # حساب ELO الكلاسيكي مع K = 32
            k = 32
            e_w = 1 / (1 + 10 ** ((r_l - r_w) / 400))
            e_l = 1 / (1 + 10 ** ((r_w - r_l) / 400))

            if is_draw:
                new_r_w = round(r_w + k * (0.5 - e_w))
                new_r_l = round(r_l + k * (0.5 - e_l))
            else:
                new_r_w = round(r_w + k * (1.0 - e_w))
                new_r_l = round(r_l + k * (0.0 - e_l))

            cursor.execute("UPDATE users SET rating = ? WHERE user_id = ?", (new_r_w, winner_id))
            cursor.execute("UPDATE users SET rating = ? WHERE user_id = ?", (new_r_l, loser_id))
            conn.commit()

    def record_game(
        self,
        white_id: int,
        white_name: str,
        black_id: int,
        black_name: str,
        mode: str,
        winner_id: Optional[int],
        result_type: str,
        pgn: str,
        moves_count: int,
    ):
        """تسجيل نهاية مباراة وتحديث إحصائيات اللاعبين"""
        now = datetime.datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # التأكد من وجود المستخدمين
            self.get_or_create_user(white_id, white_name)
            if black_id != 0:
                self.get_or_create_user(black_id, black_name)

            cursor.execute("""
                INSERT INTO games_history (
                    white_id, white_name, black_id, black_name, mode,
                    winner_id, result_type, pgn, moves_count, played_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (white_id, white_name, black_id, black_name, mode, winner_id, result_type, pgn, moves_count, now))

            # تحديث إحصائيات الفوز والخسارة
            if mode == "ai":
                player_id = white_id if black_id == 0 else black_id
                if winner_id == player_id:
                    cursor.execute("UPDATE users SET wins_vs_ai = wins_vs_ai + 1, last_played = ? WHERE user_id = ?", (now, player_id))
                elif winner_id is None:
                    cursor.execute("UPDATE users SET draws_vs_ai = draws_vs_ai + 1, last_played = ? WHERE user_id = ?", (now, player_id))
                else:
                    cursor.execute("UPDATE users SET losses_vs_ai = losses_vs_ai + 1, last_played = ? WHERE user_id = ?", (now, player_id))
            else:
                # طور PvP
                if winner_id is None:
                    cursor.execute("UPDATE users SET draws_vs_pvp = draws_vs_pvp + 1, last_played = ? WHERE user_id IN (?, ?)", (now, white_id, black_id))
                    self.update_rating_elo(white_id, black_id, is_draw=True)
                else:
                    loser_id = black_id if winner_id == white_id else white_id
                    cursor.execute("UPDATE users SET wins_vs_pvp = wins_vs_pvp + 1, last_played = ? WHERE user_id = ?", (now, winner_id))
                    cursor.execute("UPDATE users SET losses_vs_pvp = losses_vs_pvp + 1, last_played = ? WHERE user_id = ?", (now, loser_id))
                    self.update_rating_elo(winner_id, loser_id, is_draw=False)

            conn.commit()

    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """الحصول على قائمة المتصدرين حسب التصنيف (ELO)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, rating,
                       (wins_vs_pvp + wins_vs_ai) as total_wins,
                       (losses_vs_pvp + losses_vs_ai) as total_losses,
                       (draws_vs_pvp + draws_vs_ai) as total_draws
                FROM users
                ORDER BY rating DESC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]


# كائن قاعدة البيانات الموحد
db = ChessDatabase()
