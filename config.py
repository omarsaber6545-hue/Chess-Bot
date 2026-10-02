"""
إعدادات وثيمات بوت الشطرنج
Chess Bot Configuration & Themes
"""

import os
from dotenv import load_dotenv

load_dotenv()

# توكن البوت
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "")

# ثيمات رقعة الشطرنج المتوفرة
BOARD_THEMES = {
    "wood": {
        "name": "الخشبي الفاخر (Wood)",
        "square_light": "#f0d9b5",
        "square_dark": "#b58863",
        "margin": "#262421",
        "coord": "#ffffff",
        "embed_color": 0xB58863,
    },
    "emerald": {
        "name": "الزمرد الكلاسيكي (Emerald - Chess.com)",
        "square_light": "#eeeed2",
        "square_dark": "#769656",
        "margin": "#312e2b",
        "coord": "#ffffff",
        "embed_color": 0x769656,
    },
    "ocean": {
        "name": "الأزرق المحيطي (Ocean Blue)",
        "square_light": "#dee3e6",
        "square_dark": "#8ca2ad",
        "margin": "#1c2833",
        "coord": "#ffffff",
        "embed_color": 0x3498DB,
    },
    "tournament": {
        "name": "البطولات (Tournament Classic)",
        "square_light": "#eae9d2",
        "square_dark": "#4b7399",
        "margin": "#242f3d",
        "coord": "#ffffff",
        "embed_color": 0x4B7399,
    },
    "midnight": {
        "name": "الليلي الداكن (Midnight Dark)",
        "square_light": "#4a4e69",
        "square_dark": "#22223b",
        "margin": "#0b090a",
        "coord": "#f2e9e4",
        "embed_color": 0x22223B,
    },
}

DEFAULT_THEME = "emerald"

# مستويات صعوبة الذكاء الاصطناعي
DIFFICULTY_LEVELS = {
    "easy": {
        "name": "سهل (Easy)",
        "elo": "800 - 1000",
        "depth": 1,
        "blunder_chance": 0.30,
        "description": "مناسب للمبتدئين لتعلم القواعد والنقلات الأساسية.",
    },
    "medium": {
        "name": "متوسط (Medium)",
        "elo": "1300 - 1500",
        "depth": 2,
        "blunder_chance": 0.10,
        "description": "مستوى تكتيكي متوازن مع رؤية جيدة للرقعة.",
    },
    "hard": {
        "name": "صعب (Hard)",
        "elo": "1700 - 1900",
        "depth": 3,
        "blunder_chance": 0.0,
        "description": "تحدي تكتيكي قوي مع تحليل عميق للنقلات والسيطرة على المركز.",
    },
    "master": {
        "name": "خبير (Master)",
        "elo": "2100+",
        "depth": 4,
        "blunder_chance": 0.0,
        "description": "أعلى مستوى ذكاء اصطناعي مع تقييم موضعي دقيق.",
    },
}

# رموز القطع التعبيرية للإيموجي في الرسائل
PIECE_EMOJIS = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
}

# قيم القطع للحسابات
PIECE_VALUES = {
    "P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000,
    "p": 100, "n": 320, "b": 330, "r": 500, "q": 900, "k": 20000,
}
