import aiosqlite
import logging
import aiohttp
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup

from config import DATABASE_PATH, bot, cursor, TOKEN, user_states, dp, previous_states
from commands import admin_panel_handler


# Utility functions
async def check_subscription(user_id):
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        cursor = await conn.execute("SELECT telegram_id FROM channels")
        channels = await cursor.fetchall()

        for channel in channels:
            try:
                chat_member = await bot.get_chat_member(chat_id=channel[0], user_id=user_id)
                if chat_member.status in ['left', 'kicked']:
                    return False
            except Exception as e:
                logging.error(f"Error checking subscription for channel {channel[0]}: {e}")
                return False
        return True


async def ensure_subscription(message: Message):
    user_id = message.from_user.id

    if not await check_subscription(user_id):
        # If user is not subscribed, remove all buttons and show the subscription prompt
        await send_subscription_prompt(message)
        return False  # Indicate that the user is not subscribed
    return True  # User is subscribed



def get_inline_keyboard_for_channels():
    cursor.execute("SELECT telegram_id FROM channels")
    channels = cursor.fetchall()

    inline_keyboard = [
        [InlineKeyboardButton(text=f"{channel[0]}", url=f'https://t.me/{channel[0].lstrip("@")}')]
        for channel in channels
    ]
    inline_keyboard.append([InlineKeyboardButton(text="A'zo bo'ldim", callback_data='azo')])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)



async def download_video(file_id):
    file = await bot.get_file(file_id)
    download_url = f'https://api.telegram.org/file/bot{TOKEN}/{file.file_path}'

    async with aiohttp.ClientSession() as session:
        async with session.get(download_url) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                logging.error(f"Failed to download video. HTTP Status: {resp.status}")
                return None


async def save_movie_to_db(user_id):
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute('''
                INSERT INTO movies (code, title, year, genre, language, video) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_states[user_id]['code'],
                user_states[user_id]['title'],
                user_states[user_id]['year'],
                user_states[user_id]['genre'],
                user_states[user_id]['language'],
                user_states[user_id]['video_file_id']
            ))
            await conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error saving movie to database: {e}")
        return False


async def delete_previous_inline_message(chat_id, message_id):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logging.error(f"Failed to delete previous inline message: {e}")




async def send_subscription_prompt(message: Message):
    user_id = message.from_user.id

    # Remove old inline keyboard if exists
    if 'last_inline_message_id' in user_states.get(user_id, {}):
        await delete_previous_inline_message(message.chat.id, user_states[user_id]['last_inline_message_id'])

    inline_keyboard = get_inline_keyboard_for_channels()
    sent_message = await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=inline_keyboard)

    # Store the message ID for future reference
    user_states[user_id] = user_states.get(user_id, {})
    user_states[user_id]['last_inline_message_id'] = sent_message.message_id


@dp.callback_query(lambda c: c.data == 'azo')
async def callback_handler(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await check_subscription(user_id):
        await command_start_handler(callback_query.message)
    else:
        await send_subscription_prompt(callback_query.message)


async def command_start_handler(message: Message):
    user_id = message.from_user.id

    if await check_subscription(user_id):
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            cursor = await conn.execute("SELECT telegram_id FROM admins WHERE telegram_id = ?", (user_id,))
            admin = await cursor.fetchone()

        admin_button = [KeyboardButton(text="🛠 Admin panel")] if admin else []

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔍 Kino qidirish")],
                [KeyboardButton(text="🤖Telegram bot yasatish")],
                admin_button
            ],
            resize_keyboard=True
        )


        await message.answer(f"<b>👋Salom  {message.from_user.first_name}</b>\n\n <i>Kod orqali kinoni topishingiz mumkin!</i>", reply_markup=keyboard, parse_mode='html')
    else:
        await send_subscription_prompt(message)




# Function to save the previous state
def save_previous_state(user_id, current_state):
    previous_states[user_id] = current_state


# Function to handle the "back" navigation
async def go_back(user_id, message):
    previous_state = previous_states.get(user_id)


    if previous_state == 'admin_panel':
        await admin_panel_handler(message)
    elif previous_state == 'start':
        await command_start_handler(message)

    previous_states.pop(user_id, None)


async def send_channel_list(message: Message):
    cursor.execute("SELECT telegram_id FROM channels")
    channels = cursor.fetchall()

    inline_keyboard = [
        [InlineKeyboardButton(text=f"{channel[0]}", callback_data=f"delete_{channel[0]}")]
        for channel in channels
    ]
    inline_keyboard.append([InlineKeyboardButton(text="Orqaga", callback_data="back_to_admin_panel")])
    markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    await message.answer("O'chirish uchun kanalni tanlang:", reply_markup=markup)
async def send_movie_list(message: Message):
    cursor.execute("SELECT code, title FROM movies")
    movies = cursor.fetchall()

    inline_keyboard = [
        [InlineKeyboardButton(text=f"{movie[1]} - {movie[0]}", callback_data=f"delete_{movie[0]}")]
        for movie in movies
    ]
    inline_keyboard.append([InlineKeyboardButton(text="Orqaga", callback_data="back_to_admin_panel")])
    markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    await message.answer("O'chirish uchun kinoni tanlang:", reply_markup=markup)

async def show_admin_list(message: Message):
    user_id = message.from_user.id

    # Fetch all admins
    cursor.execute("SELECT telegram_id FROM admins")
    admins = cursor.fetchall()

    # Create inline keyboard with admin selection
    inline_keyboard = [
        [InlineKeyboardButton(text=f"Admin {admin[0]}", callback_data=f"delete_admin_{admin[0]}")]
        for admin in admins
    ]
    inline_keyboard.append([InlineKeyboardButton(text="Orqaga", callback_data="back_to_admin_panel")])
    markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    await message.answer("O'chirish uchun adminni tanlang:", reply_markup=markup)


@dp.callback_query(lambda c: c.data == "back_to_admin_panel")
async def back_to_admin_panel(callback_query: CallbackQuery):
    await callback_query.message.delete()
    await admin_panel_handler(callback_query.message)
