"""
محرك الذكاء الاصطناعي للشطرنج
Chess AI Engine: Built-in Alpha-Beta Minimax + Stockfish Support
"""

import os
import random
import asyncio
import chess
import chess.engine
from config import DIFFICULTY_LEVELS, PIECE_VALUES, STOCKFISH_PATH

# جداول تقييم مواضع القطع (Piece-Square Tables)
# تعطي قيمة إضافية للقطعة حسب موقعها الاستراتيجي على الرقعة
PAWN_TABLE = [
    0,   0,   0,   0,   0,   0,   0,   0,
    50,  50,  50,  50,  50,  50,  50,  50,
    10,  10,  20,  30,  30,  20,  10,  10,
    5,   5,  10,  25,  25,  10,   5,   5,
    0,   0,   0,  20,  20,   0,   0,   0,
    5,  -5, -10,   0,   0, -10,  -5,   5,
    5,  10,  10, -20, -20,  10,  10,   5,
    0,   0,   0,   0,   0,   0,   0,   0,
]

KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]

BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   5,   0,   0,   5,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,  10,   5,  10,  10,   5,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

ROOK_TABLE = [
    0,   0,   0,   0,   0,   0,   0,   0,
    5,  10,  10,  10,  10,  10,  10,   5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    0,   0,   0,   5,   5,   0,   0,   0,
]

QUEEN_TABLE = [
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
    -5,   0,   5,   5,   5,   5,   0,  -5,
    0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20,
]

KING_TABLE_MID = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20,  20,   0,   0,   0,   0,  20,  20,
    20,  30,  10,   0,   0,  10,  30,  20,
]


def evaluate_board(board: chess.Board) -> int:
    """
    تقييم الموقف من منظور اللاعب الأبيض (قيمة موجبة تعني تفوق الأبيض، سالبة تعني تفوق الأسود)
    """
    if board.is_checkmate():
        return -999999 if board.turn == chess.WHITE else 999999
    if board.is_stalemate() or board.is_insufficient_material() or board.is_fifty_moves():
        return 0

    score = 0

    for square, piece in board.piece_map().items():
        val = PIECE_VALUES.get(piece.symbol(), 0)
        table_idx = square if piece.color == chess.WHITE else chess.square_mirror(square)

        pst_val = 0
        if piece.piece_type == chess.PAWN:
            pst_val = PAWN_TABLE[table_idx]
        elif piece.piece_type == chess.KNIGHT:
            pst_val = KNIGHT_TABLE[table_idx]
        elif piece.piece_type == chess.BISHOP:
            pst_val = BISHOP_TABLE[table_idx]
        elif piece.piece_type == chess.ROOK:
            pst_val = ROOK_TABLE[table_idx]
        elif piece.piece_type == chess.QUEEN:
            pst_val = QUEEN_TABLE[table_idx]
        elif piece.piece_type == chess.KING:
            pst_val = KING_TABLE_MID[table_idx]

        total = val + pst_val
        if piece.color == chess.WHITE:
            score += total
        else:
            score -= total

    return score


def order_moves(board: chess.Board, moves):
    """ترتيب النقلات لزيادة سرعة تقليم ألفا-بيتا (Alpha-Beta Pruning)"""
    def move_priority(move: chess.Move):
        prio = 0
        # النقلات الآكلة: ضحية أكبر مقابل مهاجم أصغر (MVV-LVA)
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            victim_val = PIECE_VALUES.get(victim.symbol(), 100) if victim else 100
            attacker_val = PIECE_VALUES.get(attacker.symbol(), 100) if attacker else 100
            prio += 10000 + (victim_val * 10 - attacker_val)
        # الترقية
        if move.promotion:
            prio += 9000
        # إعطاء كش
        board.push(move)
        if board.is_check():
            prio += 500
        board.pop()
        return prio

    return sorted(moves, key=move_priority, reverse=True)


def quiescence(board: chess.Board, alpha: int, beta: int, max_ply: int = 2) -> int:
    """بحث الهدوء لمنع تأثير الأفق (Horizon Effect) على النقلات الآكلة"""
    stand_pat = evaluate_board(board)
    if not board.turn:  # إذا كان دور الأسود، نعكس المنظور
        stand_pat = -stand_pat

    if max_ply <= 0:
        return stand_pat

    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    capture_moves = [m for m in board.legal_moves if board.is_capture(m)]
    ordered = order_moves(board, capture_moves)

    for move in ordered:
        board.push(move)
        score = -quiescence(board, -beta, -alpha, max_ply - 1)
        board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


def alpha_beta(board: chess.Board, depth: int, alpha: int, beta: int, maximizing: bool) -> tuple[int, chess.Move | None]:
    """خوارزمية ميني ماكس مع تقليم ألفا-بيتا"""
    if depth == 0 or board.is_game_over():
        # استخدام بحث الهدوء في نهاية العمق
        q_val = quiescence(board, alpha, beta, max_ply=1)
        val = q_val if board.turn == chess.WHITE else -q_val
        return val, None

    best_move = None
    moves = order_moves(board, list(board.legal_moves))

    if maximizing:
        max_eval = -float("inf")
        for move in moves:
            board.push(move)
            eval_score, _ = alpha_beta(board, depth - 1, alpha, beta, False)
            board.pop()

            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move

            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = float("inf")
        for move in moves:
            board.push(move)
            eval_score, _ = alpha_beta(board, depth - 1, alpha, beta, True)
            board.pop()

            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move

            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval, best_move


class ChessAI:
    """كائن الذكاء الاصطناعي لاختيار أفضل نقلة حسب مستوى الصعوبة"""

    @classmethod
    async def get_best_move(cls, board: chess.Board, difficulty: str = "medium") -> chess.Move | None:
        """
        الحصول على نقلة الذكاء الاصطناعي بشكل غير متزامن (دون تجميد البوت)
        """
        legal = list(board.legal_moves)
        if not legal:
            return None

        # التحقق من وجود Stockfish خارجي إذا رغب المستخدم في استخدامه
        if STOCKFISH_PATH and os.path.exists(STOCKFISH_PATH):
            try:
                return await cls._get_stockfish_move(board, difficulty)
            except Exception:
                pass  # الاعتماد على المحرك المدمج تلقائياً في حال فشل المحرك الخارجي

        # تشغيل المحرك المدمج في Thread مستقل
        return await asyncio.to_thread(cls._calculate_builtin_move, board, difficulty)

    @classmethod
    def _calculate_builtin_move(cls, board: chess.Board, difficulty: str) -> chess.Move:
        config = DIFFICULTY_LEVELS.get(difficulty, DIFFICULTY_LEVELS["medium"])
        depth = config["depth"]
        blunder_chance = config.get("blunder_chance", 0.0)
        legal_moves = list(board.legal_moves)

        # احتمالية اختيار نقلة عشوائية في المستويات السهلة
        if random.random() < blunder_chance and len(legal_moves) > 1:
            # تجنب الحركات الانتحارية تماماً إن أمكن
            safe_moves = []
            for m in legal_moves:
                board.push(m)
                if not board.is_check():
                    safe_moves.append(m)
                board.pop()
            return random.choice(safe_moves or legal_moves)

        maximizing = (board.turn == chess.WHITE)
        _, move = alpha_beta(
            board=board,
            depth=depth,
            alpha=-1000000,
            beta=1000000,
            maximizing=maximizing,
        )

        return move or random.choice(legal_moves)

    @classmethod
    async def _get_stockfish_move(cls, board: chess.Board, difficulty: str) -> chess.Move:
        """استدعاء محرك Stockfish إذا تم ضبطه في الإعدادات"""
        time_limit = 0.5
        skill_levels = {"easy": 1, "medium": 6, "hard": 14, "master": 20}
        skill = skill_levels.get(difficulty, 6)

        transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
        await engine.configure({"Skill Level": skill})
        result = await engine.play(board, chess.engine.Limit(time=time_limit))
        await engine.quit()
        return result.move

    @classmethod
    async def get_hint(cls, board: chess.Board) -> tuple[chess.Move | None, str]:
        """توفير تلميح للاعب بالنقلة الأنسب وشرح مختصر لها"""
        best_move = await cls.get_best_move(board, difficulty="hard")
        if not best_move:
            return None, "لا توجد نقلات متاحة."

        san_str = board.san(best_move)
        explanation = f"النقلة المقترحة هي **{san_str}** ({best_move.uci()})."
        if board.is_capture(best_move):
            explanation += " نقلة هجومية لاقتناص قطعة."
        elif best_move.promotion:
            explanation += " ترقية لبيدقك لزيادة قوتك."
        else:
            explanation += " تطور وضعية قطعك وتحسن التحكم بالرقعة."

        return best_move, explanation
