"""
الملف الرئيسي لتشغيل بوت الشطرنج المتكامل على ديسكورد
Main Entry Point for Discord Chess Bot
"""

import sys
import asyncio
import traceback
import discord
from discord.ext import commands
import chess

from config import DISCORD_BOT_TOKEN, BOT_PREFIX
from game_manager import game_manager
from views.game_view import GameView
from views.promotion_view import PromotionView

# إعداد الصلاحيات
intents = discord.Intents.default()
intents.message_content = True  # لقراءة النقلات المكتوبة في الشات
intents.members = True          # لاقتراح الأعضاء في التحدي

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(BOT_PREFIX, "!", "؟", ""),
    intents=intents,
    help_command=None,
)


@bot.event
async def on_ready():
    """يتم استدعاء هذا الحدث عند نجاح تسجيل دخول البوت"""
    print(f"\n🤖 البوت متصل الآن باسم: {bot.user.name}#{bot.user.discriminator} (ID: {bot.user.id})")
    print(f"🌐 عدد السيرفرات المتصل بها: {len(bot.guilds)}")

    # مزامنة فورية لكل سيرفر البوت موجود فيه لتظهر أوامر السلاش في ثانية واحدة دون تأخير
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"  ⚡ تم مزامنة {len(synced)} أمر سلاش فورياً لسيرفر: '{guild.name}' (ID: {guild.id})")
        except Exception as e:
            print(f"  ⚠️ تعذر المزامنة السريعة لسيرفر {guild.name}: {e}")

    # المزامنة العامة
    try:
        await bot.tree.sync()
        print("✅ تم تأكيد المزامنة العامة لأوامر السلاش.")
    except Exception as e:
        print(f"⚠️ فشلت المزامنة العامة: {e}")

    # ضبط حالة ونشاط البوت
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name="/chess ai أو !chess | ♟️",
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)

    print("\n" + "=" * 60)
    print("♟️  بوت الشطرنج جاهز تماماً للاستخدام!")
    print("💡  الأوامر المتاحة:")
    print("    • /chess ai        أو  !chess ai")
    print("    • /chess challenge أو  !challenge @user")
    print("    • /chess help      أو  !help")
    print("==========================================================\n")


@bot.event
async def on_guild_join(guild: discord.Guild):
    """مزامنة فورية عند دخول البوت لأي سيرفر جديد"""
    try:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"🎉 انضم البوت لسيرفر جديد وتمت مزامنة الأوامر فورياً: {guild.name}")
    except Exception as e:
        print(f"⚠️ خطأ أثناء مزامنة السيرفر الجديد: {e}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    """التقاط وطباعة أي خطأ في أوامر السلاش"""
    print(f"❌ [خطأ في أمر سلاش] {error}")
    traceback.print_exc()
    try:
        msg = f"⚠️ حدث خطأ أثناء تنفيذ الأمر: `{error}`"
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception:
        pass


@bot.event
async def on_message(message: discord.Message):
    """
    الاستماع للرسائل في القنوات:
    1. طباعة الرسائل في الكونسول لتتبع المشاكل
    2. معالجة النقلات المباشرة أثناء المباريات
    3. معالجة الأوامر العادية (!chess)
    """
    if message.author.bot:
        return

    # طباعة الرسالة في الكونسول للتأكد من وصولها
    clean_content = message.content.strip()
    if clean_content:
        print(f"📩 [رسالة من {message.author.display_name} في #{message.channel}]: '{clean_content}'")

    channel_id = message.channel.id
    game = game_manager.get_game(channel_id)

    # إذا كانت هناك مباراة جارية والدور على كاتب الرسالة
    if game and not game.is_finished and game.is_user_turn(message.author.id):
        # فحص الترقية
        is_promo, from_sq, to_sq = game.is_promotion_move(clean_content)
        if is_promo:
            try:
                await message.delete()
            except discord.DiscordException:
                pass

            view_promo = PromotionView(game, from_sq, to_sq, GameView(game).on_move_submitted)
            await message.channel.send(
                f"👑 {message.author.mention} اختر القطعة للترقية:",
                view=view_promo,
                delete_after=60,
            )
            return

        # فحص إذا كان النص يمثل نقلة شطرنج صحيحة
        parsed_move = game.parse_move(clean_content)
        if parsed_move:
            try:
                await message.delete()
            except discord.DiscordException:
                pass

            print(f"♟️ تم تنفيذ نقلة من الشات: {clean_content} -> {parsed_move.uci()}")
            view = GameView(game)
            await view.process_move(parsed_move, message.channel)
            return

    # معالجة أوامر البريفكس
    await bot.process_commands(message)


async def main():
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "YOUR_DISCORD_BOT_TOKEN_HERE":
        print("❌ لم يتم ضبط التوكن في ملف .env!")
        return

    async with bot:
        await bot.load_extension("cogs.chess_cog")
        await bot.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف البوت.")
