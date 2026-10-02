"""
واجهة التحكم التفاعلية في رقعة الشطرنج
Main Interactive Chess Game View with Action Buttons
"""

import asyncio
import discord
import chess
from typing import TYPE_CHECKING, Optional
from config import BOARD_THEMES
from board_renderer import BoardRenderer
from chess_engine import ChessAI
from views.move_modal import MoveModal

if TYPE_CHECKING:
    from game_manager import ChessGame


class GameView(discord.ui.View):
    """لوحة الأزرار التفاعلية أسفل رسالة رقعة الشطرنج"""

    def __init__(self, game: "ChessGame"):
        super().__init__(timeout=None)  # تبقى نشطة طوال المباراة
        self.game = game

        # تعديل حالة بعض الأزرار حسب طور اللعب
        if self.game.is_finished:
            self._disable_gameplay_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """قفل أزرار التحكم بحيث لا يستجيب البوت إلا للاعبين المشاركين في المباراة حصراً"""
        # السماح بعرض سجل PGN لأي شخص
        custom_id = interaction.data.get("custom_id", "")
        if custom_id == "btn_pgn":
            return True

        if not self.game.is_game_player(interaction.user.id):
            p1 = self.game.white_player.display_name if self.game.white_player else "الذكاء الاصطناعي"
            p2 = self.game.black_player.display_name if self.game.black_player else "الذكاء الاصطناعي"
            await interaction.response.send_message(
                f"❌ هذه المباراة خاصة وحصرية بين **{p1}** و **{p2}**! لا يمكنك التدخل في مجرياتها.",
                ephemeral=True,
            )
            return False
        return True

    def _disable_gameplay_buttons(self):
        """تعطيل أزرار اللعب بعد نهاية المباراة"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.custom_id in ["btn_move", "btn_hint", "btn_legal", "btn_undo", "btn_draw", "btn_resign"]:
                    item.disabled = True

    @discord.ui.button(label="♟️ إلعب نقلة", style=discord.ButtonStyle.primary, row=0, custom_id="btn_move")
    async def make_move_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """فتح نافذة إدخال النقلة"""
        if self.game.is_finished:
            await interaction.response.send_message("🏁 انتهت المباراة بالفعل!", ephemeral=True)
            return

        if not self.game.is_user_turn(interaction.user.id):
            await interaction.response.send_message("❌ ليس دورك للعب الآن!", ephemeral=True)
            return

        modal = MoveModal(self.game, self.on_move_submitted)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="💡 تلميح", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_hint")
    async def hint_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """طلب تلميح لأفضل نقلة"""
        if self.game.is_finished:
            await interaction.response.send_message("🏁 انتهت المباراة بالفعل!", ephemeral=True)
            return

        if not self.game.is_user_turn(interaction.user.id):
            await interaction.response.send_message("❌ التلميح متاح فقط للاعب الذي عليه الدور حالياً!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        move, explanation = await ChessAI.get_hint(self.game.board)
        if not move:
            await interaction.followup.send("⚠️ لا توجد نقلات متاحة في الموقف الحالي.", ephemeral=True)
            return

        await interaction.followup.send(f"💡 **تلميح الذكاء الاصطناعي:**\n{explanation}", ephemeral=True)

    @discord.ui.button(label="📜 النقلات المتاحة", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_legal")
    async def legal_moves_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """عرض قائمة النقلات القانونية المتاحة"""
        moves = [self.game.board.san(m) for m in self.game.board.legal_moves]
        if not moves:
            await interaction.response.send_message("⚠️ لا توجد نقلات قانونية متاحة حالياً.", ephemeral=True)
            return

        moves_str = ", ".join(moves)
        if len(moves_str) > 1900:
            moves_str = moves_str[:1850] + "..."
        await interaction.response.send_message(f"📜 **النقلات القانونية المتاحة ({len(moves)} نقلة):**\n`{moves_str}`", ephemeral=True)

    @discord.ui.button(label="🔄 تراجع", style=discord.ButtonStyle.secondary, row=1, custom_id="btn_undo")
    async def undo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """التراجع عن آخر نقلة (متاح ضد AI)"""
        if self.game.is_finished:
            await interaction.response.send_message("🏁 انتهت المباراة بالفعل!", ephemeral=True)
            return

        if self.game.mode == "ai":
            # التحقق من أن المستخدم هو اللاعب
            player = self.game.white_player if self.game.ai_color == chess.BLACK else self.game.black_player
            if player and interaction.user.id != player.id:
                await interaction.response.send_message("❌ فقط لاعب المباراة يمكنه طلب التراجع!", ephemeral=True)
                return

            if self.game.undo_last_turn():
                await interaction.response.defer()
                await self.update_board_message(interaction.channel)
                await interaction.followup.send("🔄 تم التراجع عن النقلة بنجاح!", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ لا توجد نقلات سابقة للتراجع عنها.", ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ التراجع متاح فقط في المباريات ضد الذكاء الاصطناعي.", ephemeral=True)

    @discord.ui.button(label="🤝 طلب تعادل", style=discord.ButtonStyle.secondary, row=1, custom_id="btn_draw")
    async def offer_draw_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """عرض أو قبول التعادل"""
        if self.game.is_finished:
            await interaction.response.send_message("🏁 انتهت المباراة بالفعل!", ephemeral=True)
            return

        if self.game.mode == "ai":
            # في طور الذكاء الاصطناعي يقبل التعادل إذا كان الموقف متكافئاً
            eval_score = 0
            for piece in self.game.board.piece_map().values():
                pass
            if len(self.game.board.move_stack) > 30 and abs(len(list(self.game.board.legal_moves))) < 10:
                result_msg = self.game.agree_draw()
                self._disable_gameplay_buttons()
                await interaction.response.defer()
                await self.update_board_message(interaction.channel)
                await interaction.followup.send(f"🤖 وافق الذكاء الاصطناعي على التعادل! {result_msg}")
            else:
                await interaction.response.send_message("🤖 الذكاء الاصطناعي يرفض التعادل في هذا الموقف ويريد مواصلة القتال!", ephemeral=True)
            return

        # في طور PvP
        opponent = self.game.black_player if interaction.user.id == getattr(self.game.white_player, "id", None) else self.game.white_player
        if not opponent:
            await interaction.response.send_message("❌ أنت لست أحد طرفي هذه المباراة!", ephemeral=True)
            return

        if self.game.draw_offered_by == opponent.id:
            # قبل التعادل!
            result_msg = self.game.agree_draw()
            self._disable_gameplay_buttons()
            await interaction.response.defer()
            await self.update_board_message(interaction.channel)
            await interaction.followup.send(f"🤝 قبل {interaction.user.mention} عرض التعادل! {result_msg}")
        else:
            self.game.draw_offered_by = interaction.user.id
            await interaction.response.send_message(
                f"🤝 عرض {interaction.user.mention} التعادل! يمكن للاعب {opponent.mention} الضغط على زر **'🤝 طلب تعادل'** للموافقة.",
            )

    @discord.ui.button(label="🏳️ استسلام", style=discord.ButtonStyle.danger, row=1, custom_id="btn_resign")
    async def resign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """الاستسلام وإنهاء المباراة"""
        if self.game.is_finished:
            await interaction.response.send_message("🏁 انتهت المباراة بالفعل!", ephemeral=True)
            return

        # التحقق من أن المستخدم لاعب في المباراة
        valid_user = False
        if self.game.white_player and interaction.user.id == self.game.white_player.id:
            valid_user = True
        if self.game.black_player and interaction.user.id == self.game.black_player.id:
            valid_user = True

        if not valid_user:
            await interaction.response.send_message("❌ لست مشاركاً في هذه المباراة للاستسلام!", ephemeral=True)
            return

        result_msg = self.game.resign(interaction.user.id)
        self._disable_gameplay_buttons()
        await interaction.response.defer()
        await self.update_board_message(interaction.channel)
        await interaction.followup.send(result_msg)

    @discord.ui.button(label="🎨 تغيير المظهر", style=discord.ButtonStyle.secondary, row=2, custom_id="btn_theme")
    async def theme_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """التبديل بين ثيمات الرقعة المتاحة"""
        theme_keys = list(BOARD_THEMES.keys())
        curr_idx = theme_keys.index(self.game.theme) if self.game.theme in theme_keys else 0
        next_theme = theme_keys[(curr_idx + 1) % len(theme_keys)]
        self.game.theme = next_theme

        await interaction.response.defer()
        await self.update_board_message(interaction.channel)

    @discord.ui.button(label="📋 سجل PGN", style=discord.ButtonStyle.secondary, row=2, custom_id="btn_pgn")
    async def pgn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """عرض وتحميل سجل PGN للمباراة"""
        pgn = self.game.get_pgn_text()
        if len(pgn) > 1900:
            pgn = pgn[:1850] + "\n..."
        await interaction.response.send_message(f"📋 **سجل المباراة (PGN):**\n```\n{pgn}\n```", ephemeral=True)

    async def on_move_submitted(self, interaction: discord.Interaction, move: chess.Move):
        """معالجة النقلة بعد إرسالها من المودال أو الشات"""
        await self.process_move(move, interaction.channel)

    async def process_move(self, move: chess.Move, channel: discord.abc.Messageable):
        """تنفيذ نقلة وإعادة رسم الرقعة والتفاعل مع الذكاء الاصطناعي إن وجد"""
        # تنفيذ النقلة
        self.game.execute_move(move)

        # التحقق من نهاية اللعبة
        if self.game.is_finished:
            self._disable_gameplay_buttons()

        # تحديث رسالة الرقعة بالنقلة الجديدة
        await self.update_board_message(channel)

        # إذا كانت المباراة ضد الذكاء الاصطناعي ولم تنتهِ، دور الذكاء الاصطناعي الآن
        if not self.game.is_finished and self.game.is_ai_turn:
            # كتابة جاري التفكير وإضافة تأخير واقعي صغير
            async with channel.typing():
                await asyncio.sleep(0.6)
                ai_move = await ChessAI.get_best_move(self.game.board, self.game.ai_difficulty)
                if ai_move:
                    self.game.execute_move(ai_move)
                    if self.game.is_finished:
                        self._disable_gameplay_buttons()
                    await self.update_board_message(channel)

    async def update_board_message(self, channel: discord.abc.Messageable):
        """إعادة توليد صورة الرقعة وتحديث رسالة المباراة في ديسكورد"""
        embed = self.game.build_embed()
        orientation = self.game.get_orientation()
        board_file = BoardRenderer.get_discord_file(
            board=self.game.board,
            orientation=orientation,
            theme_name=self.game.theme,
        )

        try:
            if self.game.message:
                # حذف الصورة القديمة وإرسال الرسالة المحدثة مع الصورة الجديدة لضمان التحديث اللحظي على تطبيق ديسكورد
                await self.game.message.edit(embed=embed, attachments=[board_file], view=self)
            else:
                msg = await channel.send(file=board_file, embed=embed, view=self)
                self.game.message = msg
        except Exception:
            # في حال تعذر التعديل نرسل رسالة جديدة
            msg = await channel.send(file=board_file, embed=embed, view=self)
            self.game.message = msg
