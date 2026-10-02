"""
نافذة إدخال النقلة (Discord Modal)
Modal Dialog for Chess Move Input
"""

import discord
import chess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game_manager import ChessGame


class MoveModal(discord.ui.Modal, title="♟️ إدخال نقلة شطرنج"):
    """نافذة منبثقة تتيح للاعب كتابة نقلته بكل سهولة"""

    move_input = discord.ui.TextInput(
        label="أدخل النقلة (UCI أو SAN)",
        placeholder="مثال: e4 أو e2e4 أو Nf3 أو O-O أو exd5",
        min_length=2,
        max_length=8,
        required=True,
    )

    def __init__(self, game: "ChessGame", on_move_callback):
        super().__init__()
        self.game = game
        self.on_move_callback = on_move_callback

    async def on_submit(self, interaction: discord.Interaction):
        # التحقق من دور اللاعب
        if not self.game.is_user_turn(interaction.user.id):
            await interaction.response.send_message(
                "❌ ليس دورك للعب الآن!",
                ephemeral=True,
            )
            return

        move_text = self.move_input.value.strip()

        # فحص إذا كانت النقلة تحتاج ترقية
        is_promo, from_sq, to_sq = self.game.is_promotion_move(move_text)
        if is_promo:
            from views.promotion_view import PromotionView
            view = PromotionView(self.game, from_sq, to_sq, self.on_move_callback)
            await interaction.response.send_message(
                "👑 وصل بيدك إلى الصف الأخير! اختر القطعة التي تريد الترقية إليها:",
                view=view,
                ephemeral=True,
            )
            return

        # تحليل النقلة
        parsed_move = self.game.parse_move(move_text)
        if not parsed_move:
            # عرض اقتراحات لأقرب النقلات القانونية
            sample_legal = [self.game.board.san(m) for m in list(self.game.board.legal_moves)[:10]]
            legal_str = ", ".join(sample_legal)
            await interaction.response.send_message(
                f"❌ نقلة غير قانونية أو غير مفهومة: `{move_text}`\n"
                f"💡 بعض النقلات المتاحة لك الآن: `{legal_str}`",
                ephemeral=True,
            )
            return

        # تأكيد استلام النقلة والتنفيذ
        await interaction.response.defer()
        await self.on_move_callback(interaction, parsed_move)
