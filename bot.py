import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
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

# ==================== АНТИ-ФЛУД ====================
user_requests = defaultdict(list)

def check_flood(user_id, limit=5, seconds=10):
    """Проверка на флуд (максимум 5 запросов за 10 секунд)"""
    now = datetime.now()
    user_requests[user_id] = [t for t in user_requests[user_id] if (now - t).seconds < seconds]
    if len(user_requests[user_id]) >= limit:
        return False
    user_requests[user_id].append(now)
    return True

# ==================== СОСТОЯНИЯ ====================

class ChannelState(StatesGroup):
    waiting_link = State()
    waiting_name = State()
    waiting_category = State()
    waiting_subscribers = State()
    waiting_description = State()

class EditChannelState(StatesGroup):
    waiting_name = State()
    waiting_category = State()
    waiting_subscribers = State()
    waiting_description = State()

class AdminState(StatesGroup):
    waiting_broadcast = State()
    waiting_block_reason = State()

# ==================== КЛАВИАТУРЫ ====================

def main_menu(is_admin=False):
    """Главное меню с кнопками в ряд + админ-меню"""
    
    keyboard = [
        [
            InlineKeyboardButton(text="📖 Как это работает", callback_data="instruction"),
            InlineKeyboardButton(text="📢 Мои каналы", callback_data="my_channels")
        ],
        [
            InlineKeyboardButton(text="🔍 Найти партнёров", callback_data="find_partners"),
            InlineKeyboardButton(text="🤝 Мои партнёрства", callback_data="my_partnerships")
        ],
        [
            InlineKeyboardButton(text="⭐ Избранное", callback_data="favorites"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="my_conditions")
        ],
        [
            InlineKeyboardButton(text="👥 Рефералы", callback_data="invite_friends"),
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton(text="👑 Премиум", callback_data="premium"),
            InlineKeyboardButton(text="❓ Поддержка", callback_data="help")
        ],
    ]
    
    if is_admin:
        keyboard.append([
            InlineKeyboardButton(text="🔐 Админ-панель", callback_data="admin_panel")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def admin_menu():
    """Админ-меню с функциями"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton(text="📢 Каналы", callback_data="admin_channels"),
                InlineKeyboardButton(text="🚫 Блокировка", callback_data="admin_block")
            ],
            [
                InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
                InlineKeyboardButton(text="📥 Экспорт", callback_data="admin_export")
            ],
            [
                InlineKeyboardButton(text="👑 Премиум (в разработке)", callback_data="admin_premium_dev"),
                InlineKeyboardButton(text="⚙️ Настройки (в разработке)", callback_data="admin_settings_dev")
            ],
            [
                InlineKeyboardButton(text="🔙 Главное меню", callback_data="back")
            ]
        ]
    )

def back_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ]
    )

def category_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💼 Бизнес", callback_data="cat_business"),
                InlineKeyboardButton(text="🎮 Игры", callback_data="cat_games")
            ],
            [
                InlineKeyboardButton(text="📚 Образование", callback_data="cat_education"),
                InlineKeyboardButton(text="🎵 Музыка", callback_data="cat_music")
            ],
            [
                InlineKeyboardButton(text="📰 Новости", callback_data="cat_news"),
                InlineKeyboardButton(text="❤️ Лайфстайл", callback_data="cat_lifestyle")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back")
            ]
        ]
    )

def channel_menu(channel_id, user_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_channel_{channel_id}"),
                InlineKeyboardButton(text="📊 Статистика", callback_data=f"channel_stats_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_channel_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back")
            ]
        ]
    )

def partner_channel_menu(channel_id, owner_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Связаться", callback_data=f"contact_owner_{owner_id}"),
                InlineKeyboardButton(text="⭐ В избранное", callback_data=f"add_favorite_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back")
            ]
        ]
    )

def profile_menu(user):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats"),
                InlineKeyboardButton(text="📢 Мои каналы", callback_data="my_channels")
            ],
            [
                InlineKeyboardButton(text="👥 Рефералы", callback_data="my_referrals")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back")
            ]
        ]
    )

def premium_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💎 1 месяц (100 монет)", callback_data="buy_premium_1"),
                InlineKeyboardButton(text="💎 3 месяца (250 монет)", callback_data="buy_premium_3")
            ],
            [
                InlineKeyboardButton(text="💎 12 месяцев (800 монет)", callback_data="buy_premium_12")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back")
            ]
        ]
    )

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def extract_channel_username(link):
    """Извлекает username из ссылки с проверкой"""
    # Проверяем на опасные символы
    if re.search(r'[<>"\'/\\]', link):
        return None
    
    patterns = [
        r't\.me/([a-zA-Z0-9_]+)',
        r'@([a-zA-Z0-9_]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    return None

async def check_bot_in_channel(channel_username):
    """Проверяет, добавлен ли бот в канал"""
    try:
        chat = await bot.get_chat(f"@{channel_username}")
        member = await bot.get_chat_member(f"@{channel_username}", bot.id)
        return member.status in ["administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка проверки канала: {e}")
        return False

def is_admin(user_id):
    return user_id == ADMIN_ID

async def log_admin_action(user_id, action, details=""):
    """Логирование действий админа"""
    logging.info(f"🔐 АДМИН: {user_id} -> {action} | {details}")
    
    # Отправляем уведомление в лог-канал (если есть)
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📋 **Лог действия**\n\n"
            f"👤 Админ: @{user_id}\n"
            f"⚡ Действие: {action}\n"
            f"📝 Детали: {details}\n"
            f"🕐 Время: {datetime.now().strftime('%H:%M:%S')}"
        )
    except:
        pass

# ==================== ОБРАБОТЧИКИ ====================

@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Анти-флуд
    if not check_flood(user_id):
        await message.answer("⏳ Слишком много запросов! Подождите немного.")
        return
    
    args = message.text.split()
    referrer_code = args[1] if len(args) > 1 else None
    
    if not db.get_user(user_id):
        db.add_user(user_id, username, first_name, referrer_code, REFERRAL_BONUS)
        
        # Проверка на админа
        if is_admin(user_id):
            await message.answer(
                f"👑 **Добро пожаловать, Админ!**\n\n"
                "📢 **BoostSocialLike** — платформа для взаимного пиара!\n\n"
                "📖 Начни с инструкции, чтобы узнать как всё работает.\n\n"
                "🔐 У тебя есть доступ к админ-панели.",
                parse_mode="Markdown",
                reply_markup=main_menu(is_admin=True)
            )
        else:
            await message.answer(
                f"🎉 Добро пожаловать, {first_name}!\n\n"
                "📢 **BoostSocialLike** — платформа для взаимного пиара!\n\n"
                "📖 Начни с инструкции, чтобы узнать как всё работает.",
                parse_mode="Markdown",
                reply_markup=main_menu(is_admin=False)
            )
    else:
        user = db.get_user(user_id)
        channels = db.get_user_channels(user_id)
        
        # Проверка на админа
        if is_admin(user_id):
            await message.answer(
                f"👑 **С возвращением, Админ!**\n\n"
                f"📊 **Твоя статистика:**\n"
                f"📢 Каналов: {len(channels)}\n"
                f"👥 Рефералов: {user[5]}\n"
                f"💰 Бонусов: {user[6]} монет\n\n"
                "🔐 У тебя есть доступ к админ-панели.",
                parse_mode="Markdown",
                reply_markup=main_menu(is_admin=True)
            )
        else:
            await message.answer(
                f"👋 С возвращением, {first_name}!\n\n"
                f"📊 **Твоя статистика:**\n"
                f"📢 Каналов: {len(channels)}\n"
                f"👥 Рефералов: {user[5]}\n"
                f"💰 Бонусов: {user[6]} монет\n\n"
                "Выбери действие:",
                parse_mode="Markdown",
                reply_markup=main_menu(is_admin=False)
            )

@dp.callback_query(F.data == "back")
async def back_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if not check_flood(user_id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    await callback.message.delete()
    
    if is_admin(user_id):
        await callback.message.answer(
            "👑 Главное меню (админ-режим):",
            reply_markup=main_menu(is_admin=True)
        )
    else:
        await callback.message.answer(
            "📋 Главное меню:",
            reply_markup=main_menu(is_admin=False)
        )
    await callback.answer()

# ==================== ИНСТРУКЦИЯ ====================

@dp.callback_query(F.data == "instruction")
async def instruction(callback: types.CallbackQuery):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    text = (
        "📖 **Как это работает**\n\n"
        "1️⃣ **Добавь канал**\n"
        "   • Добавь бота в канал как администратора\n"
        "   • Нажми «Добавить канал» и введи ссылку\n\n"
        "2️⃣ **Найди партнёров**\n"
        "   • Выбери категорию\n"
        "   • Просматривай каналы для сотрудничества\n"
        "   • Связывайся с владельцами\n\n"
        "3️⃣ **Управляй каналами**\n"
        "   • Редактируй информацию\n"
        "   • Смотри статистику\n"
        "   • Удаляй каналы\n\n"
        "💡 **Совет:** Чем подробнее описание канала, тем больше партнёров!"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== ПРОФИЛЬ ====================

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    channels = db.get_user_channels(callback.from_user.id)
    
    text = (
        f"👤 **Мой профиль**\n\n"
        f"🆔 ID: {user[0]}\n"
        f"👤 Имя: @{user[1] or 'Не указано'}\n"
        f"👥 Рефералов: {user[5]}\n"
        f"💰 Бонусов: {user[6]} монет\n"
        f"📢 Каналов: {len(channels)}\n"
        f"📅 Регистрация: {user[7]}\n"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=profile_menu(user)
    )
    await callback.answer()

@dp.callback_query(F.data == "my_stats")
async def my_stats(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    channels = db.get_user_channels(callback.from_user.id)
    referrals = db.get_referrals(callback.from_user.id)
    
    text = (
        f"📊 **Моя статистика**\n\n"
        f"📢 Каналов: {len(channels)}\n"
        f"👥 Рефералов: {len(referrals)}\n"
        f"💰 Бонусов: {user[6]} монет\n"
        f"🏆 Рейтинг: #{db.get_user_rank(user[0])}\n"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

@dp.callback_query(F.data == "my_referrals")
async def my_referrals(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    referrals = db.get_referrals(user_id)
    count = db.get_referral_count(user_id)
    
    if not referrals:
        await callback.message.edit_text(
            "👥 **Мои рефералы**\n\n"
            "У тебя пока нет рефералов.\n"
            "Приглашай друзей и получай бонусы!",
            reply_markup=back_button()
        )
        await callback.answer()
        return
    
    text = f"👥 **Мои рефералы ({count})**\n\n"
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

# ==================== ПРИГЛАСИТЬ ДРУЗЕЙ ====================

@dp.callback_query(F.data == "invite_friends")
async def invite_friends(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    referral_code = user[3]
    link = f"https://t.me/{bot.username}?start={referral_code}"
    
    text = (
        f"👥 **Реферальная система**\n\n"
        f"Поделись ссылкой с друзьями и получай бонусы!\n\n"
        f"🔗 `{link}`\n\n"
        f"💰 За каждого приглашённого друга ты получаешь {REFERRAL_BONUS} монет!\n"
        f"👥 Ты уже пригласил: {user[5]} друзей\n"
        f"🪙 Заработал: {user[6]} монет"
    )
    
    share_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=f"Привет! Используй мою ссылку: {link}"),
                InlineKeyboardButton(text="📋 Копировать", callback_data=f"copy_{referral_code}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back")
            ]
        ]
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=share_kb
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("copy_"))
async def copy_referral(callback: types.CallbackQuery):
    code = callback.data.split("_")[1]
    link = f"https://t.me/{bot.username}?start={code}"
    
    await callback.answer("🔗 Ссылка скопирована!", show_alert=True)
    await callback.message.answer(f"🔗 Твоя ссылка:\n`{link}`", parse_mode="Markdown")

# ==================== ПРЕМИУМ ====================

@dp.callback_query(F.data == "premium")
async def premium(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    is_premium = db.is_premium(callback.from_user.id) if user else False
    
    text = (
        "👑 **Премиум доступ**\n\n"
        "🚀 Премиум-доступ открывает дополнительные возможности!\n\n"
        "✨ **Преимущества:**\n"
        "• 🔍 Приоритетный поиск партнёров\n"
        "• 📊 Расширенная статистика\n"
        "• 🏷️ Специальная метка в профиле\n"
        "• ⭐ Эксклюзивные предложения\n"
        "• 🚫 Без ограничений на количество каналов\n\n"
        "💳 **Стоимость:**\n"
        "• 1 месяц — 100 монет\n"
        "• 3 месяца — 250 монет\n"
        "• 12 месяцев — 800 монет\n\n"
    )
    
    if is_premium:
        text += "✅ **У вас уже есть Премиум!**"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=premium_menu()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_premium_"))
async def buy_premium(callback: types.CallbackQuery):
    months = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    if not check_flood(user_id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    prices = {1: 100, 3: 250, 12: 800}
    price = prices.get(months, 100)
    
    if user[6] < price:
        await callback.answer(f"❌ Недостаточно монет! Нужно {price}, у вас {user[6]}", show_alert=True)
        return
    
    # Списываем монеты
    db.cursor.execute("UPDATE users SET bonus_balance = bonus_balance - ? WHERE user_id = ?", (price, user_id))
    db.set_premium(user_id, months)
    db.conn.commit()
    
    await callback.message.edit_text(
        f"✅ **Премиум активирован!**\n\n"
        f"📅 На {months} месяцев\n"
        f"💳 Снято: {price} монет\n\n"
        f"🎉 Теперь у вас есть доступ ко всем преимуществам!",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== МОИ КАНАЛЫ ====================

@dp.callback_query(F.data == "my_channels")
async def my_channels(callback: types.CallbackQuery):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    channels = db.get_user_channels(callback.from_user.id)
    
    if not channels:
        await callback.message.edit_text(
            "📭 **Мои каналы**\n\n"
            "У вас пока нет каналов.\n\n"
            "➕ **Добавьте канал:**\n"
            "1. Добавьте бота в канал как администратора\n"
            "2. Нажмите «Добавить канал»\n"
            "3. Введите ссылку\n"
            "4. Бот проверит и добавит",
            reply_markup=mutual_pr_menu()
        )
        await callback.answer()
        return
    
    text = "📋 **Мои каналы**\n\n"
    for ch in channels:
        text += f"📝 {ch[2]}\n🔗 {ch[3]}\n📂 {ch[4]}\n👥 {ch[5]} подп.\n"
        text += f"👉 /channel_{ch[0]}\n\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=mutual_pr_menu()
    )
    await callback.answer()

def mutual_pr_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel"),
                InlineKeyboardButton(text="📋 Мои каналы", callback_data="my_channels")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back")
            ]
        ]
    )

# ==================== ДОБАВЛЕНИЕ КАНАЛА ====================

@dp.callback_query(F.data == "add_channel")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    # Проверяем лимит каналов (максимум 5)
    channels = db.get_user_channels(callback.from_user.id)
    is_premium = db.is_premium(callback.from_user.id)
    
    if len(channels) >= 5 and not is_premium:
        await callback.message.edit_text(
            "❌ **Лимит каналов превышен!**\n\n"
            "Максимум 5 каналов для обычных пользователей.\n"
            "Купите Премиум, чтобы добавить больше каналов!",
            reply_markup=back_button()
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "📝 **Добавление канала**\n\n"
        "1️⃣ Добавьте бота в канал как администратора\n"
        "2️⃣ Введите ссылку на канал\n\n"
        "Пример: @my_channel или t.me/my_channel",
        parse_mode="Markdown"
    )
    await state.set_state(ChannelState.waiting_link)
    await callback.answer()

@dp.message(ChannelState.waiting_link)
async def channel_link(message: types.Message, state: FSMContext):
    if not check_flood(message.from_user.id):
        await message.answer("⏳ Слишком много запросов! Подождите немного.")
        return
    
    link = message.text.strip()
    
    # Валидация ссылки
    username = extract_channel_username(link)
    if not username:
        await message.answer(
            "❌ Неправильный формат!\n\n"
            "Введите: @my_channel или t.me/my_channel",
            parse_mode="Markdown"
        )
        return
    
    # Проверка на опасные символы
    if re.search(r'[<>"\'/\\]', link):
        await message.answer("❌ Ссылка содержит недопустимые символы!")
        return
    
    checking_msg = await message.answer("⏳ Проверяю...")
    is_member = await check_bot_in_channel(username)
    await checking_msg.delete()
    
    if not is_member:
        await message.answer(
            f"❌ **Бот не в канале `@{username}`!**\n\n"
            "1. Добавьте бота в канал как администратора\n"
            "2. Дайте права на отправку сообщений\n"
            "3. Затем повторите попытку",
            parse_mode="Markdown"
        )
        return
    
    await state.update_data(username=username, link=link)
    
    await message.answer(
        f"✅ **Бот в канале `@{username}`!**\n\n"
        "Введите **название** канала:",
        parse_mode="Markdown"
    )
    await state.set_state(ChannelState.waiting_name)

@dp.message(ChannelState.waiting_name)
async def channel_name(message: types.Message, state: FSMContext):
    if not check_flood(message.from_user.id):
        await message.answer("⏳ Слишком много запросов! Подождите немного.")
        return
    
    await state.update_data(name=message.text)
    await message.answer(
        "📂 **Выберите категорию:**",
        reply_markup=category_menu()
    )
    await state.set_state(ChannelState.waiting_category)

@dp.callback_query(ChannelState.waiting_category, F.data.startswith("cat_"))
async def channel_category(callback: types.CallbackQuery, state: FSMContext):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    category = callback.data.split("_")[1]
    await state.update_data(category=category)
    
    await callback.message.edit_text(
        "👥 Введите количество подписчиков:",
        parse_mode="Markdown"
    )
    await state.set_state(ChannelState.waiting_subscribers)
    await callback.answer()

@dp.message(ChannelState.waiting_subscribers)
async def channel_subscribers(message: types.Message, state: FSMContext):
    if not check_flood(message.from_user.id):
        await message.answer("⏳ Слишком много запросов! Подождите немного.")
        return
    
    try:
        subscribers = int(message.text)
        if subscribers < 0:
            raise ValueError
    except:
        await message.answer("❌ Введите положительное число!")
        return
    
    await state.update_data(subscribers=subscribers)
    
    await message.answer(
        "📝 Введите **описание** канала:",
        parse_mode="Markdown"
    )
    await state.set_state(ChannelState.waiting_description)

@dp.message(ChannelState.waiting_description)
async def channel_description(message: types.Message, state: FSMContext):
    if not check_flood(message.from_user.id):
        await message.answer("⏳ Слишком много запросов! Подождите немного.")
        return
    
    data = await state.get_data()
    
    db.add_channel(
        message.from_user.id,
        data['name'],
        data['link'],
        data['category'],
        data['subscribers'],
        message.text
    )
    
    await message.answer(
        f"✅ **Канал добавлен!**\n\n"
        f"📝 {data['name']}\n"
        f"🔗 {data['link']}\n"
        f"📂 {data['category']}\n"
        f"👥 {data['subscribers']} подп.\n\n"
        "Теперь другие пользователи могут найти твой канал! 🚀",
        reply_markup=back_button()
    )
    await state.clear()

# ==================== ПОИСК ПАРТНЁРОВ ====================

@dp.callback_query(F.data == "find_partners")
async def find_partners(callback: types.CallbackQuery):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 **Найти партнёров**\n\n"
        "Выберите категорию:",
        reply_markup=category_menu()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def show_partners(callback: types.CallbackQuery):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    category = callback.data.split("_")[1]
    channels = db.get_channels_by_category(category)
    
    if not channels:
        await callback.message.edit_text(
            f"📭 В категории «{category}» пока нет каналов.",
            reply_markup=back_button()
        )
        await callback.answer()
        return
    
    text = f"🔍 **Партнёры в «{category}»**\n\n"
    for ch in channels[:10]:
        text += f"📝 {ch[2]}\n🔗 {ch[3]}\n👥 {ch[5]} подп.\n"
        text += f"📄 {ch[6][:50] if ch[6] else 'Нет описания'}...\n"
        text += f"👉 /channel_{ch[0]}\n\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== ИЗБРАННОЕ ====================

@dp.callback_query(F.data == "favorites")
async def favorites(callback: types.CallbackQuery):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    favorites = db.get_favorites(callback.from_user.id)
    
    if not favorites:
        await callback.message.edit_text(
            "⭐ **Избранные каналы**\n\n"
            "У вас пока нет избранных каналов.\n"
            "Добавляйте каналы через поиск партнёров!",
            reply_markup=back_button()
        )
        return
    
    text = "⭐ **Избранные каналы**\n\n"
    for fav in favorites:
        text += f"📝 {fav[2]}\n🔗 {fav[3]}\n\n"
    
    await callback.message.edit_text(text, reply_markup=back_button())
    await callback.answer()

@dp.callback_query(F.data.startswith("add_favorite_"))
async def add_favorite(callback: types.CallbackQuery):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    channel_id = int(callback.data.split("_")[2])
    channel = db.get_channel_by_id(channel_id)
    
    if not channel:
        await callback.answer("❌ Канал не найден", show_alert=True)
        return
    
    db.add_favorite(callback.from_user.id, channel_id)
    await callback.answer("⭐ Добавлено в избранное!", show_alert=True)

# ==================== МОИ ПАРТНЁРСТВА ====================

@dp.callback_query(F.data == "my_partnerships")
async def my_partnerships(callback: types.CallbackQuery):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    partnerships = db.get_user_partnerships(callback.from_user.id)
    
    if not partnerships:
        await callback.message.edit_text(
            "🤝 **Мои партнёрства**\n\n"
            "У вас пока нет активных партнёрств.\n"
            "Найдите партнёров через поиск!",
            reply_markup=back_button()
        )
        return
    
    text = "🤝 **Мои партнёрства**\n\n"
    for p in partnerships:
        text += f"📢 {p[0]} ↔ {p[1]}\n"
        text += f"📅 {p[2]}\n\n"
    
    await callback.message.edit_text(text, reply_markup=back_button())
    await callback.answer()

# ==================== МОИ УСЛОВИЯ ====================

@dp.callback_query(F.data == "my_conditions")
async def my_conditions(callback: types.CallbackQuery):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    text = (
        "⚙️ **Настройки поиска**\n\n"
        "Здесь ты можешь настроить условия для поиска партнёров:\n\n"
        "📂 **Категории:**\n"
        "• Бизнес ✅\n"
        "• Игры ✅\n"
        "• Образование ✅\n"
        "• Музыка ✅\n"
        "• Новости ✅\n\n"
        "👥 **Подписчики:**\n"
        "• От 500 до 10000\n\n"
        "🌍 **Язык:**\n"
        "• Русский\n\n"
        "⚙️ Настройка в разработке!"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== ПОМОЩЬ ====================

@dp.callback_query(F.data == "help")
async def help_callback(callback: types.CallbackQuery):
    if not check_flood(callback.from_user.id):
        await callback.answer("⏳ Подождите немного!", show_alert=True)
        return
    
    text = (
        "❓ **Поддержка**\n\n"
        "📖 **Как это работает** — инструкция\n"
        "📢 **Мои каналы** — управление каналами\n"
        "🔍 **Найти партнёров** — поиск по категориям\n"
        "🤝 **Мои партнёрства** — активные сотрудничества\n"
        "⭐ **Избранное** — сохранённые каналы\n"
        "⚙️ **Настройки** — условия поиска\n"
        "👥 **Рефералы** — приглашай друзей\n"
        "👤 **Мой профиль** — твоя статистика\n"
        "👑 **Премиум** — дополнительные функции\n\n"
        "📌 Связь с админом: @ycipo"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== АДМИН-ПАНЕЛЬ ====================

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await log_admin_action(callback.from_user.id, "Открыл админ-панель")
    
    await callback.message.edit_text(
        "🔐 **Админ-панель**\n\n"
        "Управление платформой:",
        parse_mode="Markdown",
        reply_markup=admin_menu()
    )
    await callback.answer()

# ==================== АДМИН: СТАТИСТИКА ====================

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_stats()
    
    text = (
        "📊 **Статистика платформы**\n\n"
        f"👤 Всего пользователей: {stats['total_users']}\n"
        f"👥 Всего рефералов: {stats['total_referrals']}\n"
        f"📢 Всего каналов: {stats['total_channels']}\n"
        f"💰 Всего бонусов: {stats['total_bonus']} монет\n"
        f"👑 Премиум-пользователей: {stats['total_premium']}\n"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== АДМИН: ПОЛЬЗОВАТЕЛИ ====================

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    users = db.get_all_users()
    
    text = f"👥 **Все пользователи ({len(users)})**\n\n"
    for user in users[:10]:
        text += f"👤 @{user[1] or user[0]}\n"
        text += f"   📊 Рефералов: {user[5]}\n"
        text += f"   💰 Бонусов: {user[6]}\n"
        text += f"   👑 {'✅' if user[7] else '❌'} Премиум\n\n"
    
    if len(users) > 10:
        text += f"... и ещё {len(users) - 10}"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== АДМИН: КАНАЛЫ ====================

@dp.callback_query(F.data == "admin_channels")
async def admin_channels(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    channels = db.get_all_channels()
    
    text = f"📢 **Все каналы ({len(channels)})**\n\n"
    for ch in channels[:10]:
        text += f"📝 {ch[2]}\n"
        text += f"   👤 Владелец: {ch[1]}\n"
        text += f"   👥 {ch[5]} подп.\n"
        text += f"   📂 {ch[4]}\n\n"
    
    if len(channels) > 10:
        text += f"... и ещё {len(channels) - 10}"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== АДМИН: БЛОКИРОВКА ====================

@dp.callback_query(F.data == "admin_block")
async def admin_block_menu(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🚫 **Блокировка пользователей**\n\n"
        "Команды:\n"
        "/block <user_id> — заблокировать\n"
        "/unblock <user_id> — разблокировать\n\n"
        "Чтобы узнать user_id, используй /admin_users",
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== АДМИН: РАССЫЛКА ====================

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_menu(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 **Рассылка**\n\n"
        "Отправь сообщение командой:\n"
        "/broadcast <текст>\n\n"
        "Пример: /broadcast Всем привет!",
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== АДМИН: ПРЕМИУМ (В РАЗРАБОТКЕ) ====================

@dp.callback_query(F.data == "admin_premium_dev")
async def admin_premium_dev(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👑 **Премиум-управление**\n\n"
        "🚧 **В разработке!**\n\n"
        "Здесь будет:\n"
        "• Управление премиум-пользователями\n"
        "• Назначение премиума\n"
        "• Настройка цен\n"
        "• Статистика премиум-пользователей\n\n"
        "⏳ Ожидайте обновления!",
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== АДМИН: НАСТРОЙКИ (В РАЗРАБОТКЕ) ====================

@dp.callback_query(F.data == "admin_settings_dev")
async def admin_settings_dev(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "⚙️ **Настройки платформы**\n\n"
        "🚧 **В разработке!**\n\n"
        "Здесь будет:\n"
        "• Настройка бонусов\n"
        "• Настройка лимитов\n"
        "• Управление категориями\n"
        "• Системные настройки\n\n"
        "⏳ Ожидайте обновления!",
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== АДМИН: ЭКСПОРТ ====================

@dp.callback_query(F.data == "admin_export")
async def admin_export_menu(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📥 **Экспорт данных**\n\n"
        "Команды для экспорта:\n"
        "/export_users — экспорт пользователей\n"
        "/export_channels — экспорт каналов\n"
        "/export_referrals — экспорт рефералов",
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

# ==================== АДМИН-КОМАНДЫ ====================

@dp.message(Command("block"))
async def block_user(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    try:
        user_id = int(message.text.split()[1])
        user = db.get_user(user_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        db.block_user(user_id)
        await log_admin_action(message.from_user.id, f"Заблокировал пользователя {user_id}", f"@{user[1]}")
        await message.answer(f"✅ Пользователь {user_id} заблокирован")
    except:
        await message.answer("❌ Использование: /block <user_id>")

@dp.message(Command("unblock"))
async def unblock_user(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    try:
        user_id = int(message.text.split()[1])
        db.unblock_user(user_id)
        await log_admin_action(message.from_user.id, f"Разблокировал пользователя {user_id}")
        await message.answer(f"✅ Пользователь {user_id} разблокирован")
    except:
        await message.answer("❌ Использование: /unblock <user_id>")

@dp.message(Command("broadcast"))
async def broadcast(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    text = " ".join(message.text.split()[1:])
    if not text:
        await message.answer("❌ Использование: /broadcast <текст>")
        return
    
    users = db.get_all_users()
    success = 0
    failed = 0
    
    await log_admin_action(message.from_user.id, "Отправил рассылку", f"Текст: {text[:50]}...")
    
    status_msg = await message.answer("⏳ Отправляю рассылку...")
    
    for user in users:
        try:
            await bot.send_message(user[0], f"📢 {text}")
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n"
        f"📤 Отправлено: {success}\n"
        f"❌ Не доставлено: {failed}"
    )

@dp.message(Command("export_users"))
async def export_users(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    users = db.get_all_users()
    text = "👥 Экспорт пользователей\n\n"
    for user in users:
        text += f"{user[0]}|@{user[1]}|{user[5]}|{user[6]}\n"
    
    await message.answer_document(
        document=text.encode(),
        filename=f"users_{datetime.now().strftime('%Y%m%d')}.txt"
    )

@dp.message(Command("export_channels"))
async def export_channels(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    channels = db.get_all_channels()
    text = "📢 Экспорт каналов\n\n"
    for ch in channels:
        text += f"{ch[0]}|{ch[2]}|{ch[3]}|{ch[4]}|{ch[5]}\n"
    
    await message.answer_document(
        document=text.encode(),
        filename=f"channels_{datetime.now().strftime('%Y%m%d')}.txt"
    )

# ==================== ЗАПУСК ====================

async def health_check(request):
    return web.Response(text="OK")

async def run_bot():
    logging.info("🚀 Бот запущен!")
    await dp.start_polling(bot)

async def main():
    port = int(os.environ.get("PORT", 8080))
    
    app = web.Application()
    app.router.add_get('/health', health_check)
    
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logging.info(f"✅ Веб-сервер запущен на порту {port}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
