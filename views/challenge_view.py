"""
واجهة التحدي بين لاعبين (PvP Challenge View)
"""

import discord
import random
import chess
from typing import TYPE_CHECKING
from game_manager import game_manager
from board_renderer import BoardRenderer

if TYPE_CHECKING:
    from views.game_view import GameView


class ChallengeView(discord.ui.View):
    """أزرار قبول أو رفض تحدي الشطرنج بين عضوين في السيرفر"""

    def __init__(self, challenger: discord.User | discord.Member, challenged: discord.User | discord.Member, color_choice: str, theme: str, game_view_factory):
        super().__init__(timeout=180)  # تنتهي صلاحية التحدي بعد 3 دقائق
        self.challenger = challenger
        self.challenged = challenged
        self.color_choice = color_choice
        self.theme = theme
        self.game_view_factory = game_view_factory

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        # إزالة التحدي من المدير
        game_manager.remove_challenge(self.challenged.id)

    @discord.ui.button(label="✅ قبول التحدي", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message("❌ هذا التحدي ليس موجهاً إليك!", ephemeral=True)
            return

        # تحديد الألوان
        if self.color_choice == "white":
            white_player = self.challenger
            black_player = self.challenged
        elif self.color_choice == "black":
            white_player = self.challenged
            black_player = self.challenger
        else:
            # عشوائي
            if random.choice([True, False]):
                white_player = self.challenger
                black_player = self.challenged
            else:
                white_player = self.challenged
                black_player = self.challenger

        # تعطيل أزرار التحدي فوراً
        for child in self.children:
            child.disabled = True

        await interaction.response.defer()
        await interaction.message.edit(
            content=f"⚔️ **تم قبول التحدي!** بدأت المباراة بين {self.challenger.mention} و {self.challenged.mention}!",
            view=self,
        )

        # بدء اللعبة في القناة
        game = game_manager.start_game(
            channel_id=interaction.channel_id,
            mode="pvp",
            white_player=white_player,
            black_player=black_player,
            theme=self.theme,
        )

        game_manager.remove_challenge(self.challenged.id)

        # إنشاء الرقعة والفيو
        view = self.game_view_factory(game)
        embed = game.build_embed()
        board_file = BoardRenderer.get_discord_file(
            board=game.board,
            orientation=chess.WHITE,
            theme_name=game.theme,
        )

        msg = await interaction.channel.send(file=board_file, embed=embed, view=view)
        game.message = msg

    @discord.ui.button(label="❌ رفض التحدي", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id and interaction.user.id != self.challenger.id:
            await interaction.response.send_message("❌ لا يمكنك التفاعل مع هذا التحدي!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        game_manager.remove_challenge(self.challenged.id)

        action_by = self.challenged.mention if interaction.user.id == self.challenged.id else self.challenger.mention
        await interaction.response.edit_message(
            content=f"🚫 تم إلغاء/رفض التحدي بواسطة {action_by}.",
            view=self,
        )
