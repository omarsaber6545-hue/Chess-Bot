"""
اختبار تحقق شامل لجميع أجزاء بوت الشطرنج
Comprehensive Integration Test for Discord Chess Bot
"""

import sys
import io
import chess
from config import BOARD_THEMES
from database import ChessDatabase
from board_renderer import BoardRenderer
from chess_engine import ChessAI
from game_manager import GameManager, ChessGame


def run_tests():
    print("==========================================")
    print("🧪 بدء اختبار التحقق الشامل للبوت...")
    print("==========================================")

    # 1. اختبار قاعدة البيانات
    print("[1/5] اختبار قاعدة البيانات SQLite ونظام ELO...")
    test_db = ChessDatabase(":memory:")
    u1 = test_db.get_or_create_user(1001, "PlayerWhite")
    u2 = test_db.get_or_create_user(1002, "PlayerBlack")
    assert u1["rating"] == 1200, f"Expected 1200, got {u1['rating']}"
    test_db.update_rating_elo(1001, 1002, is_draw=False)
    u1_new = test_db.get_or_create_user(1001, "PlayerWhite")
    u2_new = test_db.get_or_create_user(1002, "PlayerBlack")
    assert u1_new["rating"] > 1200, "Winner rating should increase"
    assert u2_new["rating"] < 1200, "Loser rating should decrease"
    print(f"✅ نجح اختبار قاعدة البيانات! تقييم الفائز: {u1_new['rating']} ELO، الخاسر: {u2_new['rating']} ELO")

    # 2. اختبار توليد صور الرقعة بجميع الثيمات
    print("[2/5] اختبار توليد صور الرقعة عبر PyMuPDF بجميع الثيمات الـ 5...")
    b = chess.Board()
    for theme_name in BOARD_THEMES:
        buf = BoardRenderer.render_board(b, theme_name=theme_name)
        assert len(buf.getvalue()) > 10000, f"Theme {theme_name} rendered empty image"
        print(f"  • ثيم {theme_name}: صورة سليمة بحجم {len(buf.getvalue())} بايت")
    print("✅ نجح اختبار توليد الصور لجميع الثيمات!")

    # 3. اختبار تحليل نقلات الشطرنج
    print("[3/5] اختبار فك وتحليل النقلات الذكي (UCI + SAN + المرونة)...")
    gm = GameManager()
    game = gm.start_game(channel_id=999, mode="ai", white_player=None, black_player=None)

    # تجربة e4 و e2e4
    m1 = game.parse_move("e4")
    assert m1 == chess.Move.from_uci("e2e4"), "Failed to parse e4"
    game.execute_move(m1)

    # تجربة e5
    m2 = game.parse_move("E7E5")
    assert m2 == chess.Move.from_uci("e7e5"), "Failed to parse E7E5"
    game.execute_move(m2)

    # تجربة nf3 (lowercase)
    m3 = game.parse_move("nf3")
    assert m3 == chess.Move.from_uci("g1f3"), "Failed to parse nf3"
    game.execute_move(m3)

    print("✅ نجح اختبار تحليل النقلات بكل الصيغ المرنة!")

    # 4. اختبار الذكاء الاصطناعي ومستويات الصعوبة
    print("[4/5] اختبار محرك الذكاء الاصطناعي المدمج (Alpha-Beta)...")
    ai_move = ChessAI._calculate_builtin_move(game.board, "medium")
    assert ai_move is not None, "AI failed to return a move"
    assert ai_move in game.board.legal_moves, "AI move is illegal!"
    print(f"✅ نجح اختبار الذكاء الاصطناعي! النقلة المختارة: {game.board.san(ai_move)}")

    # 5. اختبار كش مات واكتمال المباراة
    print("[5/5] اختبار الكش مات وإنهاء المباراة...")
    b_mate = chess.Board()
    # Scholar's mate
    for move_str in ["e4", "e5", "Qh5", "Nc6", "Bc4", "Nf6", "Qxf7#"]:
        m = b_mate.parse_san(move_str)
        b_mate.push(m)
    assert b_mate.is_checkmate(), "Position should be checkmate"
    buf_mate = BoardRenderer.render_board(b_mate)
    assert len(buf_mate.getvalue()) > 10000, "Mate image rendered empty"
    print("✅ تم رصد كش مات بنجاح ورسم صورة الرقعة!")

    print("\n==========================================")
    print("🎉 جميع الاختبارات (5/5) نجحت بنسبة 100%!")
    print("==========================================")


if __name__ == "__main__":
    run_tests()
