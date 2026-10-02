"""
مولد صور رقعة الشطرنج بدقة عالية
Chess Board Image Renderer using chess.svg & PyMuPDF
"""

import io
import chess
import chess.svg
import pymupdf
import discord
from config import BOARD_THEMES, DEFAULT_THEME


class BoardRenderer:
    """مسؤول عن توليد صور رقعة الشطرنج بتصميمات أنيقة ودقة عالية"""

    @staticmethod
    def render_board(
        board: chess.Board,
        orientation: chess.Color = chess.WHITE,
        theme_name: str = DEFAULT_THEME,
        arrows: list = None,
        dpi: int = 150,
        size: int = 640,
    ) -> io.BytesIO:
        """
        توليد صورة PNG لرقعة الشطرنج الحالية

        :param board: كائن لوحة الشطرنج من python-chess
        :param orientation: زاوية العرض (أبيض في الأسفل أو أسود في الأسفل)
        :param theme_name: اسم الثيم اللوني
        :param arrows: قائمة أسهم توضيحية (للتلميحات مثلاً)
        :param dpi: دقة وضوح الصورة
        :param size: حجم الرقعة بالبكسل
        :return: بايتات الصورة بصيغة PNG داخل BytesIO
        """
        theme = BOARD_THEMES.get(theme_name, BOARD_THEMES[DEFAULT_THEME])

        # آخر نقلة ملعوبة لتظليلها بلون مميز
        last_move = board.peek() if len(board.move_stack) > 0 else None

        # مربع الملك إذا كان في حالة كش ملك لتظليله باللون الأحمر
        check_square = board.king(board.turn) if board.is_check() else None

        # ألوان المربعات والإطار
        color_scheme = {
            "square light": theme["square_light"],
            "square dark": theme["square_dark"],
            "margin": theme["margin"],
            "coord": theme["coord"],
        }

        # توليد SVG عبر مكتبة chess.svg الرسمية
        svg_content = chess.svg.board(
            board=board,
            orientation=orientation,
            lastmove=last_move,
            check=check_square,
            arrows=arrows or [],
            colors=color_scheme,
            size=size,
            coordinates=True,
        )

        # تحويل SVG إلى PNG بجودة عالية وبدون أي متطلبات نظام خارجية
        doc = pymupdf.open(stream=svg_content.encode("utf-8"), filetype="svg")
        page = doc[0]
        pixmap = page.get_pixmap(dpi=dpi)
        png_bytes = pixmap.tobytes("png")
        doc.close()

        # إرجاع الصورة كـ stream في الذاكرة
        buf = io.BytesIO(png_bytes)
        buf.seek(0)
        return buf

    @classmethod
    def get_discord_file(
        cls,
        board: chess.Board,
        orientation: chess.Color = chess.WHITE,
        theme_name: str = DEFAULT_THEME,
        arrows: list = None,
        filename: str = "chess_board.png",
    ) -> discord.File:
        """إرجاع كائن discord.File جاهز للإرسال في الديسكورد"""
        buf = cls.render_board(
            board=board,
            orientation=orientation,
            theme_name=theme_name,
            arrows=arrows,
        )
        return discord.File(fp=buf, filename=filename)
