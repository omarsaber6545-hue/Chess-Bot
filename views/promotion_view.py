"""
أزرار اختيار ترقية البيدق
Pawn Promotion Selection Buttons
"""

import discord
import chess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game_manager import ChessGame


class PromotionView(discord.ui.View):
    """عرض أزرار لاختيار القطعة المراد ترقية البيدق إليها"""

    def __init__(self, game: "ChessGame", from_sq: chess.Square, to_sq: chess.Square, on_move_callback):
        super().__init__(timeout=60)
        self.game = game
        self.from_sq = from_sq
        self.to_sq = to_sq
        self.on_move_callback = on_move_callback

    async def _handle_promotion(self, interaction: discord.Interaction, piece_type: chess.PieceType):
        move = chess.Move(self.from_sq, self.to_sq, promotion=piece_type)
        if move not in self.game.board.legal_moves:
            await interaction.response.send_message("❌ هذه الترقية غير قانونية في الموقف الحالي.", ephemeral=True)
            return

        # إيقاف الأزرار
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="✅ تم تنفيذ الترقية بنجاح!", view=self)

        await self.on_move_callback(interaction, move)

    @discord.ui.button(label="♕ وزير / ملكة (Queen)", style=discord.ButtonStyle.primary, row=0)
    async def promote_queen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_promotion(interaction, chess.QUEEN)

    @discord.ui.button(label="♖ قلعة / رخ (Rook)", style=discord.ButtonStyle.secondary, row=0)
    async def promote_rook(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_promotion(interaction, chess.ROOK)

    @discord.ui.button(label="♗ فيل (Bishop)", style=discord.ButtonStyle.secondary, row=1)
    async def promote_bishop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_promotion(interaction, chess.BISHOP)

    @discord.ui.button(label="♘ حصان (Knight)", style=discord.ButtonStyle.secondary, row=1)
    async def promote_knight(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_promotion(interaction, chess.KNIGHT)
