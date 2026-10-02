"""
إدارة جلسات اللعب وحالات المباريات
Chess Game Session & State Manager
"""

import time
import datetime
from typing import Optional, Dict, Any, Tuple
import discord
import chess
from config import BOARD_THEMES, DEFAULT_THEME, DIFFICULTY_LEVELS, PIECE_EMOJIS, PIECE_VALUES
from database import db


class ChessGame:
    """كائن يمثل مباراة شطرنج فردية جارية"""

    def __init__(
        self,
        channel_id: int,
        mode: str,  # "ai" أو "pvp"
        white_player: Optional[discord.User | discord.Member],
        black_player: Optional[discord.User | discord.Member],
        ai_color: Optional[chess.Color] = None,
        ai_difficulty: str = "medium",
        theme: str = DEFAULT_THEME,
    ):
        self.channel_id = channel_id
        self.mode = mode
        self.white_player = white_player
        self.black_player = black_player
        self.ai_color = ai_color
        self.ai_difficulty = ai_difficulty
        self.theme = theme

        self.board = chess.Board()
        self.move_history: list[str] = []
        self.created_at = datetime.datetime.now()
        self.last_activity = time.time()
        self.draw_offered_by: Optional[int] = None
        self.message: Optional[discord.Message] = None
        self.is_finished = False
        self.winner: Optional[discord.User | discord.Member | str] = None
        self.finish_reason = ""

    @property
    def current_turn_player(self) -> Optional[discord.User | discord.Member | str]:
        """معرفة من عليه اللعب الآن"""
        if self.board.turn == chess.WHITE:
            return self.white_player if self.white_player else "الذكاء الاصطناعي (أبيض)"
        else:
            return self.black_player if self.black_player else "الذكاء الاصطناعي (أسود)"

    @property
    def is_ai_turn(self) -> bool:
        """هل الدور الحالي هو دور الذكاء الاصطناعي؟"""
        return self.mode == "ai" and self.board.turn == self.ai_color

    def is_user_turn(self, user_id: int) -> bool:
        """التحقق مما إذا كان الدور يخص هذا المستخدم"""
        if self.mode == "ai":
            player = self.white_player if self.ai_color == chess.BLACK else self.black_player
            return player is not None and player.id == user_id and not self.is_ai_turn
        else:
            active_player = self.white_player if self.board.turn == chess.WHITE else self.black_player
            return active_player is not None and active_player.id == user_id

    def is_game_player(self, user_id: int) -> bool:
        """التحقق مما إذا كان هذا المستخدم أحد أطراف المباراة حصراً"""
        if self.mode == "ai":
            player = self.white_player if self.ai_color == chess.BLACK else self.black_player
            return player is not None and player.id == user_id
        else:
            w_id = self.white_player.id if self.white_player else None
            b_id = self.black_player.id if self.black_player else None
            return user_id in [w_id, b_id]

    def get_orientation(self, user_id: Optional[int] = None) -> chess.Color:
        """تحديد زاوية عرض الرقعة (إذا كان اللاعب أسود تُقلب الرقعة لتسهيل الرؤية)"""
        if self.mode == "ai":
            return chess.BLACK if self.ai_color == chess.WHITE else chess.WHITE
        if user_id and self.black_player and user_id == self.black_player.id:
            return chess.BLACK
        return chess.WHITE

    def parse_move(self, text: str) -> Optional[chess.Move]:
        """
        تحليل ذكي ومرن لنقلة اللاعب (يدعم UCI و SAN بدون حساسية لحالة الأحرف)
        أمثلة: e4, e2e4, Nf3, nf3, O-O, o-o, exd5, e7e8q
        """
        clean = text.strip()
        if not clean:
            return None

        # 1. تجربة UCI المباشرة (مثل e2e4)
        try:
            m = chess.Move.from_uci(clean.lower())
            if m in self.board.legal_moves:
                return m
        except ValueError:
            pass

        # 2. تجربة SAN المباشرة
        try:
            m = self.board.parse_san(clean)
            if m in self.board.legal_moves:
                return m
        except Exception:
            pass

        # 3. مطابقة مرنة مع جميع النقلات القانونية المتاحة
        clean_lower = clean.lower()
        clean_normalized = clean_lower.replace("0-0-0", "o-o-o").replace("0-0", "o-o")

        for m in self.board.legal_moves:
            # مطابقة UCI
            if m.uci().lower() == clean_lower:
                return m
            # مطابقة SAN
            try:
                san = self.board.san(m)
                san_norm = san.lower().rstrip("+#").replace("0-0-0", "o-o-o").replace("0-0", "o-o")
                if san_norm == clean_normalized or san.lower() == clean_lower:
                    return m
            except Exception:
                continue

        return None

    def is_promotion_move(self, text: str) -> Tuple[bool, Optional[chess.Square], Optional[chess.Square]]:
        """التحقق مما إذا كانت النقلة تتطلب ترقية بيدق دون تحديد القطعة بعد"""
        clean = text.strip().lower()
        if len(clean) >= 4:
            try:
                from_sq = chess.parse_square(clean[:2])
                to_sq = chess.parse_square(clean[2:4])
                piece = self.board.piece_at(from_sq)
                if piece and piece.piece_type == chess.PAWN:
                    to_rank = chess.square_rank(to_sq)
                    if (piece.color == chess.WHITE and to_rank == 7) or (piece.color == chess.BLACK and to_rank == 0):
                        if len(clean) == 4:
                            return True, from_sq, to_sq
            except ValueError:
                pass
        return False, None, None

    def execute_move(self, move: chess.Move) -> str:
        """تنفيذ النقلة وتحديث الحالة وسجل النقلات"""
        san_text = self.board.san(move)
        self.move_history.append(san_text)
        self.board.push(move)
        self.last_activity = time.time()
        self.draw_offered_by = None  # إلغاء أي عرض تعادل سابق بعد أي نقلة

        # فحص انتهاء المباراة
        self._check_game_over()
        return san_text

    def undo_last_turn(self) -> bool:
        """التراجع عن آخر دور (نقلتين في طور AI، أو نقلة واحدة في PvP)"""
        if self.mode == "ai":
            if len(self.board.move_stack) >= 2:
                self.board.pop()
                self.board.pop()
                self.move_history.pop()
                self.move_history.pop()
                self.last_activity = time.time()
                return True
            elif len(self.board.move_stack) == 1:
                self.board.pop()
                self.move_history.pop()
                self.last_activity = time.time()
                return True
        else:
            if len(self.board.move_stack) >= 1:
                self.board.pop()
                self.move_history.pop()
                self.last_activity = time.time()
                return True
        return False

    def resign(self, player_id: int) -> str:
        """استسلام أحد اللاعبين"""
        self.is_finished = True
        if self.mode == "ai":
            self.winner = "الذكاء الاصطناعي"
            self.finish_reason = "انسحاب اللاعب"
            self._save_game_result("resignation", winner_id=0)
            return "🏳️ أعلنت استسلامك! فاز الذكاء الاصطناعي بالمباراة."
        else:
            if self.white_player and player_id == self.white_player.id:
                self.winner = self.black_player
                winner_name = self.black_player.mention if self.black_player else "الأسود"
                self._save_game_result("resignation", winner_id=self.black_player.id if self.black_player else None)
                return f"🏳️ استسلم الأبيض! مبروك الفوز للاعب {winner_name}."
            else:
                self.winner = self.white_player
                winner_name = self.white_player.mention if self.white_player else "الأبيض"
                self._save_game_result("resignation", winner_id=self.white_player.id if self.white_player else None)
                return f"🏳️ استسلم الأسود! مبروك الفوز للاعب {winner_name}."

    def agree_draw(self) -> str:
        """اتفاق اللاعبين على التعادل"""
        self.is_finished = True
        self.winner = None
        self.finish_reason = "اتفاق اللاعبين على التعادل"
        self._save_game_result("draw_agreement", winner_id=None)
        return "🤝 تم قبول عرض التعادل! انتهت المباراة بالتعادل."

    def _check_game_over(self):
        """فحص الشروط القانونية لانتهاء المباراة"""
        if self.board.is_checkmate():
            self.is_finished = True
            # الفائز هو من قام بآخر نقلة
            if self.board.turn == chess.WHITE:
                # كش مات للأبيض -> الأسود فاز
                self.winner = self.black_player if self.black_player else "الذكاء الاصطناعي"
                self.finish_reason = "كش مات (Checkmate)! فاز الأسود 🏆"
                win_id = self.black_player.id if self.black_player else (0 if self.mode == "ai" else None)
            else:
                # كش مات للأسود -> الأبيض فاز
                self.winner = self.white_player if self.white_player else "الذكاء الاصطناعي"
                self.finish_reason = "كش مات (Checkmate)! فاز الأبيض 🏆"
                win_id = self.white_player.id if self.white_player else (0 if self.mode == "ai" else None)

            self._save_game_result("checkmate", winner_id=win_id)

        elif self.board.is_stalemate():
            self.is_finished = True
            self.winner = None
            self.finish_reason = "تعادل بسبب الحصر والخنق (Stalemate)!"
            self._save_game_result("stalemate", winner_id=None)

        elif self.board.is_insufficient_material():
            self.is_finished = True
            self.winner = None
            self.finish_reason = "تعادل لعدم كفاية القطع للإماتة (Insufficient Material)!"
            self._save_game_result("insufficient_material", winner_id=None)

        elif self.board.is_fifty_moves():
            self.is_finished = True
            self.winner = None
            self.finish_reason = "تعادل بقاعدة الـ 50 نقلة دون أكل أو تحريك بيدق!"
            self._save_game_result("fifty_moves", winner_id=None)

        elif self.board.can_claim_threefold_repetition():
            self.is_finished = True
            self.winner = None
            self.finish_reason = "تعادل بسبب تكرار الوضعية 3 مرات (Threefold Repetition)!"
            self._save_game_result("threefold_repetition", winner_id=None)

    def _save_game_result(self, result_type: str, winner_id: Optional[int]):
        """حفظ سجل النتيجة في قاعدة البيانات"""
        w_id = self.white_player.id if self.white_player else 0
        w_name = self.white_player.display_name if self.white_player else "AI Bot"
        b_id = self.black_player.id if self.black_player else 0
        b_name = self.black_player.display_name if self.black_player else "AI Bot"

        pgn_text = self.get_pgn_text()
        moves_count = len(self.board.move_stack)

        try:
            db.record_game(
                white_id=w_id,
                white_name=w_name,
                black_id=b_id,
                black_name=b_name,
                mode=self.mode,
                winner_id=winner_id,
                result_type=result_type,
                pgn=pgn_text,
                moves_count=moves_count,
            )
        except Exception:
            pass

    def get_captured_pieces(self) -> Dict[str, Any]:
        """حساب القطع المأكولة وفارق النقاط المادية"""
        initial_pieces = {
            "P": 8, "N": 2, "B": 2, "R": 2, "Q": 1,
            "p": 8, "n": 2, "b": 2, "r": 2, "q": 1,
        }
        current_pieces = {k: 0 for k in initial_pieces}
        for p in self.board.piece_map().values():
            sym = p.symbol()
            if sym in current_pieces:
                current_pieces[sym] += 1

        # القطع البيضاء المفقودة (أكلها الأسود)
        captured_by_black = []
        # القطع السوداء المفقودة (أكلها الأبيض)
        captured_by_white = []

        white_score = 0
        black_score = 0

        for sym, init_count in initial_pieces.items():
            diff = init_count - current_pieces[sym]
            if diff > 0:
                emoji = PIECE_EMOJIS.get(sym, sym)
                val = PIECE_VALUES.get(sym, 0)
                if sym.isupper():  # قطعة بيضاء أكلها الأسود
                    captured_by_black.extend([emoji] * diff)
                    black_score += val * diff
                else:  # قطعة سوداء أكلها الأبيض
                    captured_by_white.extend([emoji] * diff)
                    white_score += val * diff

        material_diff = (white_score - black_score) // 100

        return {
            "white_captured": "".join(captured_by_white) or "لا توجد",
            "black_captured": "".join(captured_by_black) or "لا توجد",
            "material_diff": material_diff,
        }

    def get_pgn_text(self) -> str:
        """الحصول على نص PGN للمباراة الحالية"""
        game = chess.pgn.Game.from_board(self.board)
        game.headers["Event"] = "Discord Chess Bot Match"
        game.headers["White"] = self.white_player.display_name if self.white_player else "AI Bot"
        game.headers["Black"] = self.black_player.display_name if self.black_player else "AI Bot"
        game.headers["Date"] = self.created_at.strftime("%Y.%m.%d")
        return str(game)

    def build_embed(self) -> discord.Embed:
        """بناء رسالة Discord Embed متكاملة وتفاعلية تعرض حالة اللعبة"""
        theme_cfg = BOARD_THEMES.get(self.theme, BOARD_THEMES[DEFAULT_THEME])
        color = theme_cfg.get("embed_color", 0x769656)

        title = "♟️ مباراة شطرنج - ضد الذكاء الاصطناعي" if self.mode == "ai" else "⚔️ مباراة شطرنج - لاعب ضد لاعب (PvP)"
        embed = discord.Embed(title=title, color=color)

        # تحديد اللاعبين
        w_name = self.white_player.mention if self.white_player else "🤖 الذكاء الاصطناعي"
        b_name = self.black_player.mention if self.black_player else "🤖 الذكاء الاصطناعي"

        captures = self.get_captured_pieces()

        # معلومات الأبيض والأسود
        embed.add_field(
            name=f"⚪ الأبيض: {w_name}",
            value=f"القطع المأكولة: {captures['white_captured']}",
            inline=True,
        )
        embed.add_field(
            name=f"⚫ الأسود: {b_name}",
            value=f"القطع المأكولة: {captures['black_captured']}",
            inline=True,
        )

        # فارق النقاط
        diff = captures["material_diff"]
        diff_str = f"+{diff} للأبيض" if diff > 0 else (f"+{-diff} للأسود" if diff < 0 else "متكافئ")
        embed.add_field(name="⚖️ التفوق المادي", value=diff_str, inline=True)

        # حالة المباراة ومن عليه اللعب
        if self.is_finished:
            status_desc = f"🏁 **انتهت المباراة:** {self.finish_reason}"
        else:
            turn_indicator = "⚪ دور الأبيض" if self.board.turn == chess.WHITE else "⚫ دور الأسود"
            active_player = self.white_player if self.board.turn == chess.WHITE else self.black_player
            player_mention = active_player.mention if active_player else "الذكاء الاصطناعي"

            status_desc = f"👉 **{turn_indicator}** ({player_mention})"
            if self.board.is_check():
                status_desc += "\n⚠️ **كش ملك (Check)!**"

        embed.add_field(name="📊 حالة اللعبة", value=status_desc, inline=False)

        # آخر نقلة وعدد النقلات
        move_num = (len(self.board.move_stack) + 1) // 2
        last_move_text = self.move_history[-1] if self.move_history else "لم تبدأ بعد"
        embed.add_field(name="⏱️ آخر نقلة", value=f"النقلة {move_num}: `{last_move_text}`", inline=True)

        if self.mode == "ai":
            diff_info = DIFFICULTY_LEVELS.get(self.ai_difficulty, {})
            embed.add_field(name="🤖 مستوى الذكاء", value=f"{diff_info.get('name', 'متوسط')}", inline=True)

        embed.set_image(url="attachment://chess_board.png")
        embed.set_footer(text=f"الثيم: {theme_cfg['name']} • اكتب النقلة بالشات مباشرة (مثال: e4 أو e2e4) أو اضغط ♟️")

        return embed


class GameManager:
    """المتحكم المركزي في جميع المباريات الجارية والتحديات المعلقة"""

    def __init__(self):
        self.games: Dict[int, ChessGame] = {}  # channel_id -> ChessGame
        self.pending_challenges: Dict[int, Dict[str, Any]] = {}  # challenged_user_id -> challenge data

    def get_game(self, channel_id: int) -> Optional[ChessGame]:
        return self.games.get(channel_id)

    def start_game(
        self,
        channel_id: int,
        mode: str,
        white_player: Optional[discord.User | discord.Member],
        black_player: Optional[discord.User | discord.Member],
        ai_color: Optional[chess.Color] = None,
        ai_difficulty: str = "medium",
        theme: str = DEFAULT_THEME,
    ) -> ChessGame:
        game = ChessGame(
            channel_id=channel_id,
            mode=mode,
            white_player=white_player,
            black_player=black_player,
            ai_color=ai_color,
            ai_difficulty=ai_difficulty,
            theme=theme,
        )
        self.games[channel_id] = game
        return game

    def end_game(self, channel_id: int):
        if channel_id in self.games:
            del self.games[channel_id]

    def add_challenge(self, challenger: discord.User, challenged: discord.User, channel_id: int, color_choice: str, theme: str):
        self.pending_challenges[challenged.id] = {
            "challenger": challenger,
            "challenged": challenged,
            "channel_id": channel_id,
            "color_choice": color_choice,
            "theme": theme,
            "time": time.time(),
        }

    def get_challenge(self, challenged_id: int) -> Optional[Dict[str, Any]]:
        return self.pending_challenges.get(challenged_id)

    def remove_challenge(self, challenged_id: int):
        if challenged_id in self.pending_challenges:
            del self.pending_challenges[challenged_id]


# المدير العام للمباريات
game_manager = GameManager()
