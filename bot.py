import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from config import BOT_TOKEN, ADMIN_ID, REFERRAL_BONUS
from database import db

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== СОСТОЯНИЯ ====================

class ChannelState(StatesGroup):
    waiting_name = State()
    waiting_link = State()
    waiting_category = State()
    waiting_subscribers = State()

# ==================== КЛАВИАТУРЫ ====================

def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Моя реферальная ссылка", callback_data="referral_link")],
            [InlineKeyboardButton(text="👥 Мои рефералы", callback_data="my_referrals")],
            [InlineKeyboardButton(text="💰 Мой баланс", callback_data="my_balance")],
            [InlineKeyboardButton(text="🏆 Топ рефералов", callback_data="leaderboard")],
            [InlineKeyboardButton(text="📢 Взаимный пиар", callback_data="mutual_pr")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
        ]
    )

def back_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ]
    )

def referral_link_menu(referral_code):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Копировать ссылку", callback_data=f"copy_{referral_code}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ]
    )

def mutual_pr_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Добавить канал", callback_data="add_channel")],
            [InlineKeyboardButton(text="📋 Мои каналы", callback_data="my_channels")],
            [InlineKeyboardButton(text="🔍 Найти партнёров", callback_data="find_partners")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ]
    )

def category_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📈 Бизнес", callback_data="cat_business")],
            [InlineKeyboardButton(text="🎮 Игры", callback_data="cat_games")],
            [InlineKeyboardButton(text="📚 Образование", callback_data="cat_education")],
            [InlineKeyboardButton(text="🎵 Музыка", callback_data="cat_music")],
            [InlineKeyboardButton(text="📰 Новости", callback_data="cat_news")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ]
    )

# ==================== ОБРАБОТЧИКИ ====================

@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    args = message.text.split()
    referrer_code = args[1] if len(args) > 1 else None
    
    if not db.get_user(user_id):
        db.add_user(user_id, username, first_name, referrer_code, REFERRAL_BONUS)
        await message.answer(
            f"🎉 Добро пожаловать, {first_name}!\n\n"
            "Ты получил уникальную реферальную ссылку!\n"
            "Приглашай друзей и зарабатывай бонусы!",
            reply_markup=main_menu()
        )
    else:
        await message.answer(
            "👋 С возвращением!",
            reply_markup=main_menu()
        )

@dp.callback_query(F.data == "back")
async def back_callback(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "📋 Главное меню:",
        reply_markup=main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "referral_link")
async def referral_link(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("❌ Пользователь не найден")
        await callback.answer()
        return
    
    referral_code = user[3]
    link = f"https://t.me/{bot.username}?start={referral_code}"
    
    text = (
        f"🔗 **Твоя реферальная ссылка:**\n\n"
        f"`{link}`\n\n"
        f"👥 Приглашено: {user[5]} рефералов\n"
        f"💰 Бонусов: {user[6]} монет\n\n"
        f"За каждого реферала ты получаешь {REFERRAL_BONUS} монет!"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=referral_link_menu(referral_code)
    )
    await callback.answer()

@dp.callback_query(F.data == "my_referrals")
async def my_referrals(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    referrals = db.get_referrals(user_id)
    count = db.get_referral_count(user_id)
    
    if not referrals:
        await callback.message.edit_text(
            "👥 У тебя пока нет рефералов.\n"
            "Приглашай друзей и получай бонусы!",
            reply_markup=back_button()
        )
        await callback.answer()
        return
    
    text = f"👥 **Твои рефералы ({count})**\n\n"
    for ref in referrals[:20]:
        text += f"• @{ref[1] or ref[0]} — {ref[2]}\n"
    
    if len(referrals) > 20:
        text += f"\n... и ещё {len(referrals) - 20}"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

@dp.callback_query(F.data == "my_balance")
async def my_balance(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("❌ Пользователь не найден")
        await callback.answer()
        return
    
    text = (
        f"💰 **Твой баланс**\n\n"
        f"👥 Рефералов: {user[5]}\n"
        f"🪙 Бонусов: {user[6]} монет\n"
        f"🏆 {REFERRAL_BONUS} монет за каждого реферала"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

@dp.callback_query(F.data == "leaderboard")
async def leaderboard(callback: types.CallbackQuery):
    leaders = db.get_leaderboard(10)
    
    if not leaders:
        await callback.message.edit_text(
            "🏆 Топ рефералов пока пуст.\n"
            "Приглашай друзей и становись лидером!",
            reply_markup=back_button()
        )
        await callback.answer()
        return
    
    text = "🏆 **Топ рефералов**\n\n"
    for i, leader in enumerate(leaders, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} @{leader[1] or leader[0]} — {leader[2]} реф. ({leader[3]} монет)\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

@dp.callback_query(F.data == "mutual_pr")
async def mutual_pr(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📢 **Взаимный пиар**\n\n"
        "Здесь ты можешь:\n"
        "• 📝 Добавить свой канал в систему\n"
        "• 🔍 Найти партнёров по тематике\n"
        "• 📊 Управлять партнёрствами\n\n"
        "Выбери действие:",
        parse_mode="Markdown",
        reply_markup=mutual_pr_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "add_channel")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 **Добавление канала**\n\n"
        "Введите название вашего канала:",
        parse_mode="Markdown"
    )
    await state.set_state(ChannelState.waiting_name)
    await callback.answer()

@dp.message(ChannelState.waiting_name)
async def channel_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("🔗 Теперь введите ссылку на канал:")
    await state.set_state(ChannelState.waiting_link)

@dp.message(ChannelState.waiting_link)
async def channel_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer(
        "📂 **Выберите категорию канала:**",
        reply_markup=category_menu()
    )
    await state.set_state(ChannelState.waiting_category)

@dp.callback_query(ChannelState.waiting_category, F.data.startswith("cat_"))
async def channel_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[1]
    await state.update_data(category=category)
    
    await callback.message.edit_text(
        "👥 Введите количество подписчиков (примерно):",
        parse_mode="Markdown"
    )
    await state.set_state(ChannelState.waiting_subscribers)
    await callback.answer()

@dp.message(ChannelState.waiting_subscribers)
async def channel_subscribers(message: types.Message, state: FSMContext):
    try:
        subscribers = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    
    db.add_channel(
        message.from_user.id,
        data['name'],
        data['link'],
        data['category'],
        subscribers
    )
    
    await message.answer(
        f"✅ **Канал добавлен!**\n\n"
        f"📝 Название: {data['name']}\n"
        f"🔗 Ссылка: {data['link']}\n"
        f"📂 Категория: {data['category']}\n"
        f"👥 Подписчиков: {subscribers}",
        reply_markup=back_button()
    )
    await state.clear()

@dp.callback_query(F.data == "my_channels")
async def my_channels(callback: types.CallbackQuery):
    channels = db.get_user_channels(callback.from_user.id)
    
    if not channels:
        await callback.message.edit_text(
            "📭 У вас пока нет каналов.\n"
            "Добавьте свой канал через «Добавить канал».",
            reply_markup=back_button()
        )
        await callback.answer()
        return
    
    text = "📋 **Ваши каналы**\n\n"
    for ch in channels:
        text += f"📝 {ch[2]}\n🔗 {ch[3]}\n📂 {ch[4]}\n👥 {ch[5]} подп.\n\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

@dp.callback_query(F.data == "find_partners")
async def find_partners(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🔍 **Поиск партнёров**\n\n"
        "Выберите категорию для поиска:",
        reply_markup=category_menu()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def show_partners(callback: types.CallbackQuery):
    category = callback.data.split("_")[1]
    channels = db.get_channels_by_category(category)
    
    if not channels:
        await callback.message.edit_text(
            f"📭 В категории «{category}» пока нет каналов.\n"
            "Добавьте свой первый!",
            reply_markup=back_button()
        )
        await callback.answer()
        return
    
    text = f"🔍 **Партнёры в категории «{category}»**\n\n"
    for ch in channels[:10]:
        text += f"📝 {ch[2]}\n🔗 {ch[3]}\n👥 {ch[5]} подп.\n\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

@dp.callback_query(F.data == "help")
async def help_callback(callback: types.CallbackQuery):
    text = (
        "❓ **Помощь**\n\n"
        "🤝 **Взаимный пиар**\n"
        "Добавьте свой канал, найдите партнёров и продвигайтесь вместе!\n\n"
        "🔗 **Реферальная система**\n"
        f"За каждого приглашённого друга вы получаете {REFERRAL_BONUS} монет.\n\n"
        "🏆 **Топ рефералов**\n"
        "Соревнуйтесь с другими пользователями!\n\n"
        "📌 Связь с админом: /admin"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("copy_"))
async def copy_referral(callback: types.CallbackQuery):
    code = callback.data.split("_")[1]
    link = f"https://t.me/{bot.username}?start={code}"
    
    await callback.answer("🔗 Ссылка скопирована!", show_alert=True)
    await callback.message.answer(f"🔗 Твоя ссылка:\n`{link}`", parse_mode="Markdown")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    stats = db.get_stats()
    
    text = (
        "👑 **Админ-панель**\n\n"
        f"👤 Всего пользователей: {stats['total_users']}\n"
        f"👥 Всего рефералов: {stats['total_referrals']}\n"
        f"📢 Всего каналов: {stats['total_channels']}"
    )
    
    await message.answer(text, parse_mode="Markdown")

# ==================== ЗАПУСК С ВЕБ-СЕРВЕРОМ ====================

async def health_check(request):
    """Эндпоинт для проверки работоспособности"""
    return web.Response(text="OK")

async def run_bot():
    """Запуск бота в фоновом режиме"""
    logging.info("🚀 Бот запущен!")
    await dp.start_polling(bot)

async def main():
    # Получаем порт от Render
    port = int(os.environ.get("PORT", 8080))
    
    # Создаем веб-приложение
    app = web.Application()
    app.router.add_get('/health', health_check)
    
    # Запускаем бота в фоновом режиме
    loop = asyncio.get_event_loop()
    task = loop.create_task(run_bot())
    
    # Запускаем веб-сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logging.info(f"✅ Веб-сервер запущен на порту {port}")
    
    # Держим сервер активным
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
