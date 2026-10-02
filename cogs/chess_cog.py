"""
أوامر الشطرنج التفاعلية (Slash Commands Cog)
Chess Commands Cog for Discord Slash Commands
"""

import random
import discord
from discord import app_commands
from discord.ext import commands
import chess

from config import BOARD_THEMES, DEFAULT_THEME, DIFFICULTY_LEVELS
from game_manager import game_manager
from board_renderer import BoardRenderer
from chess_engine import ChessAI
from database import db
from views.game_view import GameView
from views.challenge_view import ChallengeView
from views.promotion_view import PromotionView


class ChessCog(commands.Cog, name="الشطرنج"):
    """مجموعة أوامر الشطرنج المتكاملة"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # مجموعة أوامر /chess
    chess_group = app_commands.Group(name="chess", description="أوامر لعبة الشطرنج المتكاملة")

    @chess_group.command(name="ai", description="🤖 بدء مباراة شطرنج ضد الذكاء الاصطناعي")
    @app_commands.describe(
        difficulty="اختر مستوى صعوبة الذكاء الاصطناعي",
        color="اختر لونك (أبيض أو أسود أو عشوائي)",
        theme="اختر مظهر ورسومات الرقعة",
    )
    @app_commands.choices(
        difficulty=[
            app_commands.Choice(name="سهل (Easy - 900 ELO)", value="easy"),
            app_commands.Choice(name="متوسط (Medium - 1400 ELO)", value="medium"),
            app_commands.Choice(name="صعب (Hard - 1800 ELO)", value="hard"),
            app_commands.Choice(name="خبير (Master - 2100+ ELO)", value="master"),
        ],
        color=[
            app_commands.Choice(name="⚪ أبيض (White)", value="white"),
            app_commands.Choice(name="⚫ أسود (Black)", value="black"),
            app_commands.Choice(name="🎲 عشوائي (Random)", value="random"),
        ],
        theme=[
            app_commands.Choice(name="الزمرد الأخضر (Emerald)", value="emerald"),
            app_commands.Choice(name="الخشبي الفاخر (Wood)", value="wood"),
            app_commands.Choice(name="الأزرق المحيطي (Ocean)", value="ocean"),
            app_commands.Choice(name="البطولات الكلاسيكي (Tournament)", value="tournament"),
            app_commands.Choice(name="الليلي الداكن (Midnight)", value="midnight"),
        ],
    )
    async def play_ai(
        self,
        interaction: discord.Interaction,
        difficulty: str = "medium",
        color: str = "white",
        theme: str = DEFAULT_THEME,
    ):
        channel_id = interaction.channel_id

        # التحقق من وجود مباراة نشطة في نفس القناة
        existing_game = game_manager.get_game(channel_id)
        if existing_game and not existing_game.is_finished:
            await interaction.response.send_message(
                "⚠️ توجد مباراة نشطة بالفعل في هذه القناة! يمكنك إنهاؤها بكتابة `/chess resign` أو لعبها حتى النهاية.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        # تحديد اللون
        if color == "random":
            user_color = random.choice([chess.WHITE, chess.BLACK])
        elif color == "white":
            user_color = chess.WHITE
        else:
            user_color = chess.BLACK

        ai_color = chess.BLACK if user_color == chess.WHITE else chess.WHITE
        white_player = interaction.user if user_color == chess.WHITE else None
        black_player = interaction.user if user_color == chess.BLACK else None

        # بدء اللعبة
        game = game_manager.start_game(
            channel_id=channel_id,
            mode="ai",
            white_player=white_player,
            black_player=black_player,
            ai_color=ai_color,
            ai_difficulty=difficulty,
            theme=theme,
        )

        view = GameView(game)

        # إذا اختار اللاعب الأسود، يقوم الذكاء الاصطناعي بلعب النقلة الأولى كأبيض
        if ai_color == chess.WHITE:
            ai_move = await ChessAI.get_best_move(game.board, difficulty)
            if ai_move:
                game.execute_move(ai_move)

        orientation = game.get_orientation(interaction.user.id)
        embed = game.build_embed()
        board_file = BoardRenderer.get_discord_file(
            board=game.board,
            orientation=orientation,
            theme_name=game.theme,
        )

        msg = await interaction.followup.send(file=board_file, embed=embed, view=view)
        game.message = msg

    @chess_group.command(name="challenge", description="⚔️ تحدي لاعب آخر في السيرفر لمباراة شطرنج")
    @app_commands.describe(
        opponent="الشخص الذي تريد تحديه",
        color="اختر لونك في المباراة",
        theme="مظهر الرقعة",
    )
    @app_commands.choices(
        color=[
            app_commands.Choice(name="⚪ أبيض (White)", value="white"),
            app_commands.Choice(name="⚫ أسود (Black)", value="black"),
            app_commands.Choice(name="🎲 عشوائي (Random)", value="random"),
        ],
        theme=[
            app_commands.Choice(name="الزمرد الأخضر (Emerald)", value="emerald"),
            app_commands.Choice(name="الخشبي الفاخر (Wood)", value="wood"),
            app_commands.Choice(name="الأزرق المحيطي (Ocean)", value="ocean"),
            app_commands.Choice(name="البطولات الكلاسيكي (Tournament)", value="tournament"),
            app_commands.Choice(name="الليلي الداكن (Midnight)", value="midnight"),
        ],
    )
    async def challenge_user(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member,
        color: str = "random",
        theme: str = DEFAULT_THEME,
    ):
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("❌ لا يمكنك تحدي نفسك! للعب الفردي استخدم `/chess ai`.", ephemeral=True)
            return

        if opponent.bot:
            await interaction.response.send_message("❌ لا يمكنك تحدي بوت ديسكورد! للعب ضد الكمبيوتر استخدم `/chess ai`.", ephemeral=True)
            return

        channel_id = interaction.channel_id
        existing_game = game_manager.get_game(channel_id)
        if existing_game and not existing_game.is_finished:
            await interaction.response.send_message("⚠️ توجد مباراة جارية حالياً في هذه القناة.", ephemeral=True)
            return

        await interaction.response.defer()

        # تسجيل التحدي
        game_manager.add_challenge(
            challenger=interaction.user,
            challenged=opponent,
            channel_id=channel_id,
            color_choice=color,
            theme=theme,
        )

        view = ChallengeView(
            challenger=interaction.user,
            challenged=opponent,
            color_choice=color,
            theme=theme,
            game_view_factory=lambda g: GameView(g),
        )

        embed = discord.Embed(
            title="⚔️ دعوة تحدي شطرنج جديدة!",
            description=(
                f"أرسل {interaction.user.mention} تحدياً في الشطرنج إلى {opponent.mention}!\n\n"
                f"• **اللون:** {color}\n"
                f"• **الثيم:** {theme}\n\n"
                f"هل تقبل التحدي يا {opponent.mention}؟"
            ),
            color=0xF1C40F,
        )
        embed.set_footer(text="تنتهي صلاحية التحدي تلقائياً بعد 3 دقائق.")

        await interaction.followup.send(content=f"{opponent.mention}", embed=embed, view=view)

    @chess_group.command(name="move", description="♟️ تنفيذ نقلة في المباراة الجارية بالقناة")
    @app_commands.describe(notation="أدخل النقلة بالصيغة القياسية أو الإحداثيات (مثال: e4, e2e4, Nf3, O-O)")
    async def make_move(self, interaction: discord.Interaction, notation: str):
        game = game_manager.get_game(interaction.channel_id)
        if not game or game.is_finished:
            await interaction.response.send_message("⚠️ لا توجد مباراة شطرنج نشطة في هذه القناة حالياً.", ephemeral=True)
            return

        if not game.is_user_turn(interaction.user.id):
            await interaction.response.send_message("❌ ليس دورك للعب الآن!", ephemeral=True)
            return

        # فحص إذا كانت النقلة تحتاج ترقية
        is_promo, from_sq, to_sq = game.is_promotion_move(notation)
        if is_promo:
            view_promo = PromotionView(game, from_sq, to_sq, GameView(game).on_move_submitted)
            await interaction.response.send_message("👑 اختر القطعة للترقية:", view=view_promo, ephemeral=True)
            return

        parsed = game.parse_move(notation)
        if not parsed:
            await interaction.response.send_message(f"❌ النقلة `{notation}` غير قانونية أو غير مفهومة في هذا الموقف.", ephemeral=True)
            return

        await interaction.response.defer()
        game_view = GameView(game)
        await game_view.process_move(parsed, interaction.channel)
        await interaction.followup.send(f"✅ تم تنفيذ النقلة: `{notation}`", ephemeral=True)

    @chess_group.command(name="board", description="🖼️ إعادة إرسال رقعة الشطرنج الحالية في القناة")
    async def show_board(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)
        if not game:
            await interaction.response.send_message("⚠️ لا توجد مباراة شطرنج في هذه القناة.", ephemeral=True)
            return

        await interaction.response.defer()
        view = GameView(game)
        orientation = game.get_orientation(interaction.user.id)
        embed = game.build_embed()
        board_file = BoardRenderer.get_discord_file(
            board=game.board,
            orientation=orientation,
            theme_name=game.theme,
        )

        msg = await interaction.followup.send(file=board_file, embed=embed, view=view)
        game.message = msg

    @chess_group.command(name="hint", description="💡 الحصول على تلميح ذكي للنقلة القادمة")
    async def get_hint(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)
        if not game or game.is_finished:
            await interaction.response.send_message("⚠️ لا توجد مباراة نشطة في هذه القناة.", ephemeral=True)
            return

        if not game.is_user_turn(interaction.user.id):
            await interaction.response.send_message("❌ التلميح متاح فقط للاعب الذي عليه الدور حالياً!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        move, explanation = await ChessAI.get_hint(game.board)
        if move:
            await interaction.followup.send(f"💡 **تلميح الذكاء الاصطناعي:**\n{explanation}", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ لا توجد نقلات متاحة في هذا الموقف.", ephemeral=True)

    @chess_group.command(name="legal", description="📜 عرض جميع النقلات القانونية المتاحة لموقفك الحالي")
    async def show_legal(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)
        if not game or game.is_finished:
            await interaction.response.send_message("⚠️ لا توجد مباراة نشطة في هذه القناة.", ephemeral=True)
            return

        moves = [game.board.san(m) for m in game.board.legal_moves]
        if not moves:
            await interaction.response.send_message("⚠️ لا توجد نقلات متاحة.", ephemeral=True)
            return

        moves_str = ", ".join(moves)
        if len(moves_str) > 1900:
            moves_str = moves_str[:1850] + "..."
        await interaction.response.send_message(f"📜 **النقلات القانونية المتاحة ({len(moves)} نقلة):**\n`{moves_str}`", ephemeral=True)

    @chess_group.command(name="resign", description="🏳️ الاستسلام وإنهاء المباراة الحالية في القناة")
    async def resign_cmd(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)
        if not game or game.is_finished:
            await interaction.response.send_message("⚠️ لا توجد مباراة نشطة للاستسلام منها.", ephemeral=True)
            return

        # التحقق من أن المستخدم لاعب
        user_is_player = False
        if game.white_player and interaction.user.id == game.white_player.id:
            user_is_player = True
        if game.black_player and interaction.user.id == game.black_player.id:
            user_is_player = True

        if not user_is_player:
            await interaction.response.send_message("❌ أنت لست أحد طرفي هذه المباراة!", ephemeral=True)
            return

        await interaction.response.defer()
        res_msg = game.resign(interaction.user.id)
        view = GameView(game)
        await view.update_board_message(interaction.channel)
        await interaction.followup.send(res_msg)

    @chess_group.command(name="pgn", description="📋 استخراج سجل المباراة بصيغة PGN الرسمية")
    async def export_pgn(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)
        if not game:
            await interaction.response.send_message("⚠️ لا توجد مباراة حالية.", ephemeral=True)
            return

        pgn = game.get_pgn_text()
        if len(pgn) > 1900:
            pgn = pgn[:1850] + "\n..."
        await interaction.response.send_message(f"📋 **سجل المباراة (PGN):**\n```\n{pgn}\n```", ephemeral=True)

    @chess_group.command(name="stats", description="📊 عرض إحصائياتك الشخصية أو إحصائيات لاعب آخر")
    @app_commands.describe(user="اللاعب الذي تريد رؤية إحصائياته (اختياري)")
    async def view_stats(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = db.get_or_create_user(target.id, target.display_name)

        embed = discord.Embed(
            title=f"📊 إحصائيات الشطرنج - {target.display_name}",
            color=0x3498DB,
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="🏆 التصنيف (ELO)", value=f"**{data['rating']}**", inline=False)
        embed.add_field(
            name="🤖 ضد الذكاء الاصطناعي",
            value=f"✅ فوز: `{data['wins_vs_ai']}`\n❌ خسارة: `{data['losses_vs_ai']}`\n🤝 تعادل: `{data['draws_vs_ai']}`",
            inline=True,
        )
        embed.add_field(
            name="⚔️ لاعب ضد لاعب (PvP)",
            value=f"✅ فوز: `{data['wins_vs_pvp']}`\n❌ خسارة: `{data['losses_vs_pvp']}`\n🤝 تعادل: `{data['draws_vs_pvp']}`",
            inline=True,
        )

        total_games = (
            data['wins_vs_ai'] + data['losses_vs_ai'] + data['draws_vs_ai'] +
            data['wins_vs_pvp'] + data['losses_vs_pvp'] + data['draws_vs_pvp']
        )
        embed.add_field(name="📈 إجمالي المباريات", value=f"`{total_games}` مباراة", inline=False)

        await interaction.response.send_message(embed=embed)

    @chess_group.command(name="leaderboard", description="🏅 عرض أفضل 10 لاعبين في السيرفر حسب التصنيف ELO")
    async def leaderboard(self, interaction: discord.Interaction):
        leaders = db.get_leaderboard(limit=10)
        if not leaders:
            await interaction.response.send_message("⚠️ لم يتم تسجيل أي مباريات بعد في السيرفر.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏅 لوحة الشرف - أفضل لاعبي الشطرنج",
            color=0xF1C40F,
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(leaders):
            prefix = medals[i] if i < 3 else f"`#{i+1}`"
            lines.append(
                f"{prefix} **{row['username']}** — تصنيف: **{row['rating']}** ELO | "
                f"فوز: `{row['total_wins']}` | خسارة: `{row['total_losses']}`"
            )

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)

    @chess_group.command(name="fen", description="🔍 عرض أي وضعية شطرنج من خلال كود FEN")
    @app_commands.describe(fen="كود FEN لوضعية الشطرنج")
    async def show_fen(self, interaction: discord.Interaction, fen: str):
        await interaction.response.defer()
        try:
            b = chess.Board(fen)
        except ValueError:
            await interaction.followup.send("❌ كود FEN غير صالح!", ephemeral=True)
            return

        file = BoardRenderer.get_discord_file(board=b, theme_name=DEFAULT_THEME)
        turn_str = "الأبيض" if b.turn == chess.WHITE else "الأسود"

        embed = discord.Embed(
            title="🔍 استعراض وضعية من كود FEN",
            description=f"• الدور: **{turn_str}**\n• كود FEN:\n`{fen}`",
            color=0x2ECC71,
        )
        embed.set_image(url="attachment://chess_board.png")
        await interaction.followup.send(file=file, embed=embed)

    @chess_group.command(name="help", description="📖 دليل استخدام بوت الشطرنج وكيفية اللعب")
    async def chess_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="♟️ دليل استخدام بوت الشطرنج المتكامل",
            description=(
                "مرحباً بك في بوت الشطرنج الذكي! يمكنك اللعب ضد الذكاء الاصطناعي أو منافسة أصدقائك في السيرفر مع صور ديناميكية عالية الدقة للرقعة بعد كل نقلة.\n\n"
                "### 🎮 أوامر بدء اللعب:\n"
                "• `/chess ai` - بدء مباراة ضد الذكاء الاصطناعي (سهل، متوسط، صعب، خبير).\n"
                "• `/chess challenge @user` - تحدي أي عضو في السيرفر لمباراة ثنائية.\n"
                "• `/chess board` - إعادة إظهار الرقعة الحالية في القناة.\n"
                "• `/chess stats` - عرض إحصائياتك وتصنيفك التنافسي (ELO).\n"
                "• `/chess leaderboard` - ترتيب أفضل اللاعبين في السيرفر.\n"
                "• `/chess help` - فتح هذا الدليل.\n\n"
                "### 🕹️ كيف تلعب نقلتك؟\n"
                "1. **بالأزرار:** اضغط على زر **'♟️ إلعب نقلة'** أسفل صورة الرقعة واكتب نقلتك.\n"
                "2. **بالشات مباشرة:** اكتب النقلة مباشرة في رسالة عادية في القناة (مثال: `e4` أو `e2e4` أو `Nf3` أو `O-O`) وسيتعرف عليها البوت تلقائياً!\n"
                "3. **بالأمر:** اكتب `/chess move notation:e4`.\n\n"
                "### 🔘 الأزرار التفاعلية:\n"
                "• 💡 **تلميح:** يحلل لك الموقف ويقترح أفضل نقلة استراتيجية.\n"
                "• 📜 **النقلات المتاحة:** يعرض لك كل النقلات القانونية المسموحة لموقفك.\n"
                "• 🔄 **تراجع:** للتراجع عن النقلة في مباريات الذكاء الاصطناعي.\n"
                "• 🤝 **طلب تعادل:** لتقديم أو قبول التعادل في مباريات اللاعبين.\n"
                "• 🏳️ **استسلام:** للاستسلام وإعلان فوز الخصم.\n"
                "• 🎨 **تغيير المظهر:** للتبديل بين 5 ألوان وتصاميم فخمة للرقعة."
            ),
            color=0x769656,
        )
        embed.set_footer(text="استمتع باللعب وأظهر براعتك التكتيكية!")
        await interaction.response.send_message(embed=embed)

    # ========================================================
    # أوامر البريفكس التقليدية (!chess, !ai, !شطرنج)
    # ========================================================

    @commands.command(name="chess", aliases=["شطرنج", "play", "لعب"])
    async def prefix_chess(self, ctx: commands.Context, subcmd: str = "ai", *args):
        """بدء الشطرنج بالأوامر النصية التقليدية (!chess ai)"""
        sub = subcmd.lower()
        if sub in ["ai", "ذكاء", "كمبيوتر", "bot"]:
            diff = args[0].lower() if len(args) > 0 and args[0].lower() in ["easy", "medium", "hard", "master"] else "medium"
            color = args[1].lower() if len(args) > 1 and args[1].lower() in ["white", "black", "random"] else "white"

            existing = game_manager.get_game(ctx.channel.id)
            if existing and not existing.is_finished:
                await ctx.send("⚠️ توجد مباراة نشطة بالفعل في هذه القناة! اكتب `!resign` للاستسلام أو أكمل اللعب.")
                return

            user_color = chess.WHITE if color == "white" else (chess.BLACK if color == "black" else random.choice([chess.WHITE, chess.BLACK]))
            ai_color = chess.BLACK if user_color == chess.WHITE else chess.WHITE
            white_player = ctx.author if user_color == chess.WHITE else None
            black_player = ctx.author if user_color == chess.BLACK else None

            game = game_manager.start_game(
                channel_id=ctx.channel.id,
                mode="ai",
                white_player=white_player,
                black_player=black_player,
                ai_color=ai_color,
                ai_difficulty=diff,
            )

            if ai_color == chess.WHITE:
                ai_move = await ChessAI.get_best_move(game.board, diff)
                if ai_move:
                    game.execute_move(ai_move)

            view = GameView(game)
            orientation = game.get_orientation(ctx.author.id)
            embed = game.build_embed()
            board_file = BoardRenderer.get_discord_file(
                board=game.board,
                orientation=orientation,
                theme_name=game.theme,
            )
            msg = await ctx.send(file=board_file, embed=embed, view=view)
            game.message = msg

        elif sub in ["board", "رقعة"]:
            await self.prefix_board(ctx)
        elif sub in ["hint", "تلميح"]:
            await self.prefix_hint(ctx)
        elif sub in ["resign", "استسلام"]:
            await self.prefix_resign(ctx)
        elif sub in ["help", "مساعدة"]:
            await self.prefix_help(ctx)
        else:
            await ctx.send(
                "💡 **طريقة استخدام أوامر الشطرنج السريعة:**\n"
                "• `!chess ai` أو `!ai` لبدء مباراة ضد الذكاء الاصطناعي\n"
                "• `!challenge @user` لتحدي صديق\n"
                "• `!board` لإعادة إظهار الرقعة\n"
                "• `!hint` للحصول على تلميح\n"
                "• `!stats` لعرض إحصائياتك"
            )

    @commands.command(name="ai", aliases=["ذكاء"])
    async def prefix_ai_shortcut(self, ctx: commands.Context, diff: str = "medium", color: str = "white"):
        await self.prefix_chess(ctx, "ai", diff, color)

    @commands.command(name="board", aliases=["رقعة"])
    async def prefix_board(self, ctx: commands.Context):
        game = game_manager.get_game(ctx.channel.id)
        if not game:
            await ctx.send("⚠️ لا توجد مباراة شطرنج نشطة في هذه القناة.")
            return

        view = GameView(game)
        orientation = game.get_orientation(ctx.author.id)
        embed = game.build_embed()
        board_file = BoardRenderer.get_discord_file(
            board=game.board,
            orientation=orientation,
            theme_name=game.theme,
        )
        msg = await ctx.send(file=board_file, embed=embed, view=view)
        game.message = msg

    @commands.command(name="hint", aliases=["تلميح"])
    async def prefix_hint(self, ctx: commands.Context):
        game = game_manager.get_game(ctx.channel.id)
        if not game or game.is_finished:
            await ctx.send("⚠️ لا توجد مباراة نشطة.")
            return

        move, exp = await ChessAI.get_hint(game.board)
        if move:
            await ctx.send(f"💡 **تلميح:** {exp}")
        else:
            await ctx.send("⚠️ لا توجد نقلات متاحة.")

    @commands.command(name="resign", aliases=["استسلام"])
    async def prefix_resign(self, ctx: commands.Context):
        game = game_manager.get_game(ctx.channel.id)
        if not game or game.is_finished:
            await ctx.send("⚠️ لا توجد مباراة نشطة للاستسلام منها.")
            return

        res = game.resign(ctx.author.id)
        view = GameView(game)
        await view.update_board_message(ctx.channel)
        await ctx.send(res)

    @commands.command(name="challenge", aliases=["تحدي"])
    async def prefix_challenge(self, ctx: commands.Context, opponent: discord.Member):
        if opponent.id == ctx.author.id:
            await ctx.send("❌ لا يمكنك تحدي نفسك!")
            return

        game_manager.add_challenge(ctx.author, opponent, ctx.channel.id, "random", DEFAULT_THEME)
        view = ChallengeView(ctx.author, opponent, "random", DEFAULT_THEME, lambda g: GameView(g))
        await ctx.send(f"⚔️ {opponent.mention} أرسل لك {ctx.author.mention} تحدي شطرنج!", view=view)

    @commands.command(name="stats", aliases=["احصائيات"])
    async def prefix_stats(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        data = db.get_or_create_user(target.id, target.display_name)
        embed = discord.Embed(title=f"📊 إحصائيات الشطرنج - {target.display_name}", color=0x3498DB)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🏆 التصنيف (ELO)", value=f"**{data['rating']}**", inline=False)
        embed.add_field(
            name="🤖 ضد الذكاء الاصطناعي",
            value=f"✅ فوز: `{data['wins_vs_ai']}` | ❌ خسارة: `{data['losses_vs_ai']}` | 🤝 تعادل: `{data['draws_vs_ai']}`",
            inline=False,
        )
        embed.add_field(
            name="⚔️ لاعب ضد لاعب (PvP)",
            value=f"✅ فوز: `{data['wins_vs_pvp']}` | ❌ خسارة: `{data['losses_vs_pvp']}` | 🤝 تعادل: `{data['draws_vs_pvp']}`",
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.command(name="help", aliases=["مساعدة"])
    async def prefix_help(self, ctx: commands.Context):
        await ctx.send(
            "📖 **أوامر بوت الشطرنج:**\n"
            "• `!ai` أو `/chess ai` — بدء مباراة ضد الكمبيوتر\n"
            "• `!challenge @user` أو `/chess challenge` — تحدي صديق\n"
            "• `!board` أو `/chess board` — إظهار الرقعة\n"
            "• `!hint` — تلميح بالنقلة القادمة\n"
            "• `!resign` — استسلام\n"
            "• `!stats` — عرض إحصائياتك وتصنيفك ELO\n\n"
            "♟️ **طريقة اللعب:** اكتب النقلة مباشرة بالشات (مثال: `e4` أو `Nf3` أو `e2e4` أو `O-O`) أو اضغط زر '♟️ إلعب نقلة' أسفل صورة الرقعة!"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ChessCog(bot))
