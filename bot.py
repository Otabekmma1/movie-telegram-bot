import sqlite3
import asyncio
import aiohttp
import logging
import aiosqlite
import sys
import re
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery

# Configuration
TOKEN = "7511166749:AAEXfRoxFc-LD2UYSb5HczJY8i-3oUCQVSY"  # Replace with your actual bot token
DATABASE_PATH = 'movie_bot.db'

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Setup logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# SQLite connection
conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()

# Create necessary tables
cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY,
        telegram_id TEXT UNIQUE
    )
''')
# telegram_id = '5541564692'  # Qo'shmoqchi bo'lgan adminning Telegram ID sini kiriting
# cursor.execute('''
#     INSERT INTO admins (telegram_id) VALUES (?)
# ''', (telegram_id,))
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        telegram_id TEXT UNIQUE,
        username TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY,
        telegram_id TEXT UNIQUE,
        channel_name TEXT,
        channel_url TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY,
        code TEXT UNIQUE,
        title TEXT,
        year INTEGER,
        genre TEXT,
        language TEXT,
        video TEXT
    )
''')
conn.commit()

# User state management
user_states = {}

# Track previous states for back functionality
previous_states = {}

# Foydalanuvchilarning a'zolik arizalari


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
    # Kanal nomi va channel_url'ni olish
    cursor.execute("SELECT channel_name, channel_url FROM channels")
    channels = cursor.fetchall()

    inline_keyboard = []
    for channel in channels:
        channel_name, channel_url = channel
        # Kanal URL'sini to'g'ridan-to'g'ri qo'llash
        inline_keyboard.append([InlineKeyboardButton(text=f"{channel_name}", url=channel_url)])

    # "A'zo bo'ldim" tugmasi
    inline_keyboard.append([InlineKeyboardButton(text="A'zo bo'ldim", callback_data='azo')])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def bosh_sahifa_keyboard():
    buttons = [
        [KeyboardButton(text="🏠 Bosh menyu")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def only_back_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Orqaga")]], resize_keyboard=True)

def admin_keyboard():
    buttons = [
        [KeyboardButton(text="➕ Kino qo'shish"), KeyboardButton(text="❌ Kino o'chirish")],
        [KeyboardButton(text="➕ Kanal qo'shish"), KeyboardButton(text="❌ Kanal o'chirish")],
        [KeyboardButton(text="👥Foydalanuvchilarga xabar yuborish")],
        [KeyboardButton(text="➕ Admin qo'shish"), KeyboardButton(text="❌ Admin o'chirish")],
        [KeyboardButton(text="🏠 Bosh menyu")]

    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


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


# Handlers
@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username  # Retrieve the username

    async with aiosqlite.connect(DATABASE_PATH) as conn:
        await conn.execute("INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)", (user_id, username))
        await conn.commit()

    if not await ensure_subscription(message):
        return  # Stop further execution if the user is not subscribed

    await command_start_handler(message, message.from_user.first_name)



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
        await command_start_handler(callback_query.message, callback_query.from_user.first_name)
    else:
        await send_subscription_prompt(callback_query.message)

async def command_start_handler(message: Message, first_name: str):
    user_id = message.from_user.id

    if await check_subscription(user_id):
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.execute("SELECT telegram_id FROM admins WHERE telegram_id = ?", (user_id,)) as cursor:
                admin = await cursor.fetchone()

            # Optionally, retrieve username for display
            async with conn.execute("SELECT username FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
                user = await cursor.fetchone()
                username = user[0] if user else 'Unknown'

        admin_button = [KeyboardButton(text="🛠 Admin panel")] if admin else []

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔍 Kino qidirish")],
                [KeyboardButton(text="🤖 Telegram bot yasatish")],
                admin_button
            ],
            resize_keyboard=True
        )

        await message.answer(f"<b>👋 Salom {first_name}</b>\n\n<i>Kod orqali kinoni topishingiz mumkin!</i>", reply_markup=keyboard, parse_mode='html')
    else:
        await send_subscription_prompt(message)



@dp.message(lambda message: message.text == "🏠 Bosh menyu")
async def bosh(message:Message):
    await command_start_handler(message, message.from_user.first_name)

@dp.message(lambda message: message.text == "🛠 Admin panel")
async def admin_panel_handler(message: Message):
    user_id = message.from_user.id

    # Check if the user is an admin in the database
    cursor.execute("SELECT telegram_id FROM admins WHERE telegram_id = ?", (user_id,))
    admin = cursor.fetchone()


    if admin:
        save_previous_state(user_id, 'start')
        await message.answer("Admin paneliga xush kelibsiz. Tanlang:", reply_markup=admin_keyboard())
    else:
        # Deny access if the user is not an admin
        await message.answer("Siz admin emassiz. Bu bo'limga kira olmaysiz.")


@dp.message(lambda message: message.text == "🔍 Kino qidirish")
async def search_movie_request(message: Message):
    # Ensure the user is subscribed before proceeding
    if not await ensure_subscription(message):
        return  # Stop further execution if the user is not subscribed

    user_id = message.from_user.id
    user_states[user_id] = {'state': 'searching_movie'}
    await message.answer("<i>Kino kodini yuboring...</i>", reply_markup=bosh_sahifa_keyboard(), parse_mode='html')

@dp.message(lambda message: message.text == "🤖 Telegram bot yasatish")
async def telegram_service_request(message: Message):
    user_id = message.from_user.id
    t = ("<b>🤖Telegram bot yaratish xizmati🤖</b>\n\n"
         "Admin: @otabek_mma1\n\n"
         "<i>Adminga bot nima haqida\n"
         "bot qanday vazifalarni bajarish kerak\n"
         "toliq malumot yozib qo'ying</i>\n\n"
         "Shunga qarab narxi kelishiladi")
    await message.answer(text=t, parse_mode='html')


@dp.message(lambda message: message.text == "➕ Kino qo'shish")
async def add_movie_start(message: Message):
    save_previous_state(message.from_user.id, 'admin_panel')
    user_states[message.from_user.id] = {'state': 'adding_movie', 'step': 'title'}
    await message.answer("Kino nomini yuboring.", reply_markup=only_back_keyboard())


@dp.message(lambda message: message.text == "❌ Kino o'chirish")
async def delete_movie_request(message: Message):
    save_previous_state(message.from_user.id, 'admin_panel')
    user_states[message.from_user.id] = 'delete_movie'
    await send_movie_list(message)



@dp.message(lambda message: message.text == "➕ Kanal qo'shish")
async def add_channel_request(message: Message):
    save_previous_state(message.from_user.id, 'admin_panel')
    user_states[message.from_user.id] = {'state': 'add_channel'}
    await message.answer("Kanal ID'sini yuboring:", reply_markup=only_back_keyboard())
@dp.message(lambda message: message.text == "❌ Kanal o'chirish")
async def delete_channel_request(message: Message):
    save_previous_state(message.from_user.id, 'admin_panel')
    user_states[message.from_user.id] = 'delete_channel'
    await send_channel_list(message)


@dp.message(lambda message: message.text == "🔙 Orqaga")
async def handle_back_button(message: Message):
    user_id = message.from_user.id
    await admin_panel_handler(message)


@dp.message(lambda message: message.text == "👥Foydalanuvchilarga xabar yuborish")
async def broadcast_message_request(message: Message):
    user_states[message.from_user.id] = 'broadcast_message'
    await message.answer("Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:", reply_markup=only_back_keyboard())


@dp.message(lambda message: message.text == "➕ Admin qo'shish")
async def add_admin_start(message: Message):
    user_id = message.from_user.id

    # Check if the user is an admin
    cursor.execute("SELECT telegram_id FROM admins WHERE telegram_id = ?", (user_id,))
    admin = cursor.fetchone()

    if admin:
        user_states[user_id] = {'state': 'adding_admin'}
        await message.answer("Yangi admin telegram id sini yuboring (masalan: 123456789).",
                             reply_markup=only_back_keyboard())
    else:
        await message.answer("Siz admin emassiz, yangi admin qo'shish imkoniyatingiz yo'q.")


@dp.message(lambda message: message.text == "❌ Admin o'chirish")
async def delete_admin_start(message: Message):
    user_id = message.from_user.id

    # Check if the user is an admin
    cursor.execute("SELECT telegram_id FROM admins WHERE telegram_id = ?", (user_id,))
    admin = cursor.fetchone()


    if admin:
        user_states[user_id] = {'state': 'deleting_admin'}
        await show_admin_list(message)
    else:
        await message.answer("Siz admin emassiz, admin o'chirish imkoniyatingiz yo'q.")


@dp.message(lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get('state') == 'add_channel')
async def handle_channel_id(message: Message):
    user_id = message.from_user.id
    channel_id = message.text.strip()

    if re.match(r'^-100\d+$', channel_id):
        user_states[user_id] = {
            'channel_id': channel_id,
            'state': 'awaiting_channel_name'
        }
        await message.answer("Kanal nomini kiriting:", reply_markup=only_back_keyboard())
    else:
        await message.answer("Iltimos, to'g'ri formatda kanal ID'sini kiriting (masalan: -1001234567890).",
                             reply_markup=only_back_keyboard())

@dp.message(lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get('state') == 'awaiting_channel_name')
async def handle_channel_name(message: Message):
    user_id = message.from_user.id
    channel_name = message.text.strip()

    if isinstance(user_states.get(user_id), dict):
        user_states[user_id]['channel_name'] = channel_name
        user_states[user_id]['state'] = 'awaiting_channel_url'
        await message.answer("Kanal URL'sini kiriting (masalan: https://t.me/+tWL4NhIUHFZiMjNi):", reply_markup=only_back_keyboard())
    else:
        await message.answer("Xatolik: foydalanuvchi holati topilmadi.", reply_markup=only_back_keyboard())

@dp.message(lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get('state') == 'awaiting_channel_url')
async def handle_channel_url(message: Message):
    user_id = message.from_user.id
    channel_url = message.text.strip()

    # Validate the channel URL format
    url_pattern = re.compile(r'^https://t.me/[\w+_-]+$')
    if not url_pattern.match(channel_url):
        await message.answer("Iltimos, to'g'ri formatdagi kanal URL'sini kiriting (masalan: https://t.me/+tWL4NhIUHFZiMjNi).",
                             reply_markup=only_back_keyboard())
        return

    print(f"User States: {user_states}")
    print(f"Channel ID: {user_states[user_id].get('channel_id')}")
    print(f"Channel Name: {user_states[user_id].get('channel_name')}")
    print(f"Channel URL: {channel_url}")

    try:
        channel_id = user_states[user_id].get('channel_id')
        channel_name = user_states[user_id].get('channel_name')
        if channel_id and channel_name and channel_url:
            cursor.execute("INSERT INTO channels (channel_name, telegram_id, channel_url) VALUES (?, ?, ?)",
                           (channel_name, channel_id, channel_url))
            conn.commit()
            await message.answer("Kanal muvaffaqiyatli qo'shildi!", reply_markup=admin_keyboard())
            # Clear user state
            user_states[user_id] = {'state': 'admin_panel'}
        else:
            await message.answer("Kanal ID, nom yoki URL topilmadi.", reply_markup=admin_keyboard())
    except sqlite3.IntegrityError:
        await message.answer("Bu kanal allaqachon mavjud!", reply_markup=admin_keyboard())
    except Exception as e:
        print(f"Exception details: {e}")
        await message.answer(f"Xatolik yuz berdi: {e}", reply_markup=admin_keyboard())
@dp.callback_query(lambda c: c.data and c.data.startswith("delete_"))
async def handle_channel_deletion(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    channel_id = callback_query.data[len("delete_"):].strip()

    # Kanalni o'chirish
    try:
        cursor.execute("DELETE FROM channels WHERE telegram_id = ?", (channel_id,))
        conn.commit()
        await callback_query.message.answer("Kanal muvaffaqiyatli o'chirildi.", reply_markup=admin_keyboard())
    except Exception as e:
        await callback_query.message.answer(f"Xatolik yuz berdi: {e}", reply_markup=admin_keyboard())

    # CallbackQuery'dan foydalanib xabarni o'chirish
    await callback_query.message.delete()




@dp.message(
    lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get(
        'state') == 'deleting_admin'
)
@dp.callback_query(lambda c: c.data.startswith("delete_admin_"))
async def handle_delete_admin_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    admin_id = callback_query.data[len("delete_admin_"):].strip()

    # Delete the admin from the database
    try:
        cursor.execute("DELETE FROM admins WHERE telegram_id = ?", (admin_id,))
        conn.commit()

        if cursor.rowcount > 0:
            await callback_query.message.answer(f"Admin {admin_id} muvaffaqiyatli o'chirildi.")
        else:
            await callback_query.message.answer(f"{admin_id} adminlar ro'yxatida topilmadi.")
    except Exception as e:
        await callback_query.message.answer(f"Xatolik yuz berdi: {e}")

    # Clear the state and return to the admin panel
    user_states.pop(user_id, None)
    await callback_query.message.delete()
    await admin_panel_handler(callback_query.message)


@dp.message(
    lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get(
        'state') == 'adding_admin'
)
async def handle_add_admin(message: Message):
    user_id = message.from_user.id
    username = message.text.strip().lstrip('@')  # Remove '@' if provided


    # Fetch user info based on the username
    try:
        user = await bot.get_chat(username)
        new_admin_id = user.id
    except Exception as e:
        await message.answer(f"Foydalanuvchini topib bo'lmadi. Xato: {e}")
        return

    # Insert the new admin into the database
    try:
        cursor.execute("INSERT INTO admins (telegram_id) VALUES (?)", (new_admin_id,))
        conn.commit()
        await message.answer(f"Yangi admin {username} muvaffaqiyatli qo'shildi.")
    except sqlite3.IntegrityError:
        await message.answer("Bu foydalanuvchi allaqachon admin.")
    except Exception as e:
        await message.answer(f"Admin qo'shishda xatolik yuz berdi: {e}")


    # Clear the state
    user_states.pop(user_id, None)
    await admin_panel_handler(message)
@dp.message(lambda message: isinstance(user_states.get(message.from_user.id), str) and user_states[message.from_user.id] == 'broadcast_message')
async def broadcast_message_to_users(message: Message):
    broadcast_text = message.text

    # Fetch all user IDs (You need to have a table that stores user IDs)
    cursor.execute("SELECT telegram_id FROM users")  # Replace with your actual users table and column
    users = cursor.fetchall()

    # Send the message to all users
    for user in users:
        try:
            await bot.send_message(chat_id=user[0], text=broadcast_text)
        except Exception as e:
            logging.error(f"Failed to send message to user {user[0]}: {e}")

    # Confirm the message has been sent
    await message.answer("Xabar barcha foydalanuvchilarga muvaffaqiyatli yuborildi.", reply_markup=admin_keyboard())
    user_states.pop(message.from_user.id, None)


@dp.message(
    lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get(
        'state') == 'adding_movie')
async def add_movie(message: Message):
    user_id = message.from_user.id
    state = user_states[user_id]['step']

    if message.text == "🔙 Orqaga":
        await admin_panel_handler(message)
        return

    if state == 'title':
        user_states[user_id]['title'] = message.text
        user_states[user_id]['step'] = 'year'
        await message.answer("Kino yilini yuboring.", reply_markup=only_back_keyboard())
    elif state == 'year':
        try:
            user_states[user_id]['year'] = int(message.text)
            user_states[user_id]['step'] = 'genre'
            await message.answer("Kino janrini yuboring.", reply_markup=only_back_keyboard())
        except ValueError:
            await message.answer("Yil raqam bo'lishi kerak. Iltimos, qaytadan kiriting.")
    elif state == 'genre':
        user_states[user_id]['genre'] = message.text
        user_states[user_id]['step'] = 'language'
        await message.answer("Kino tilini yuboring.", reply_markup=only_back_keyboard())
    elif state == 'language':
        user_states[user_id]['language'] = message.text
        user_states[user_id]['step'] = 'code'
        await message.answer("Kino kodini yuboring.", reply_markup=only_back_keyboard())
    elif state == 'code':
        user_states[user_id]['code'] = message.text
        user_states[user_id]['step'] = 'video'
        await message.answer("Kino videosini yuklang (faqat MP4 format).", reply_markup=only_back_keyboard())
    elif state == 'video':
        if message.video and message.video.mime_type == 'video/mp4':
            # Get the file ID of the uploaded video
            file_id = message.video.file_id


            # Save the movie details including the video file ID to the database
            user_states[user_id]['video_file_id'] = file_id
            if await save_movie_to_db(user_id):
                await message.answer(f"Kino muvaffaqiyatli qo'shildi: {user_states[user_id]['title']}")
            else:
                await message.answer("Kino qo'shishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

            # Clear user state and go back to the admin panel
            user_states.pop(user_id, None)
            await admin_panel_handler(message)
        else:
            await message.answer("Iltimos, MP4 formatidagi videoni yuboring.")
@dp.message(lambda message: message.text == "❌ Kino o'chirish")
async def delete_movie_request(message: Message):
    save_previous_state(message.from_user.id, 'admin_panel')
    user_states[message.from_user.id] = 'delete_movie'
    await send_movie_list(message)

@dp.callback_query(lambda c: c.data and c.data.startswith("delete_"))
async def handle_movie_deletion(callback_query: CallbackQuery):
    movie_code = callback_query.data[len("delete_"):].strip()
    logging.info(f"Attempting to delete movie with code: {movie_code}")


    try:
        query = "DELETE FROM movies WHERE code = ?"
        logging.info(f"Executing query: {query} with params: ({movie_code},)")
        cursor.execute(query, (movie_code,))
        conn.commit()

        if cursor.rowcount > 0:
            await callback_query.message.answer("Kino muvaffaqiyatli o'chirildi.", reply_markup=admin_keyboard())
        else:
            await callback_query.message.answer("Kino topilmadi yoki allaqachon o'chirilgan.", reply_markup=admin_keyboard())

    except Exception as e:
        logging.error(f"Error deleting movie: {e}")
        await callback_query.message.answer(f"Xatolik yuz berdi: {e}", reply_markup=admin_keyboard())

    await callback_query.message.delete()




# Function to save the previous state
def save_previous_state(user_id, current_state):
    previous_states[user_id] = current_state



async def send_channel_list(message: Message):
    cursor.execute("SELECT channel_name, telegram_id FROM channels")
    channels = cursor.fetchall()

    inline_keyboard = [
        [InlineKeyboardButton(text=f"{channel[0]}", callback_data=f"delete_{channel[1]}")]
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

@dp.message(lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get('state') == 'searching_movie')
async def search_movie_by_code(message: Message):
    user_id = message.from_user.id
    movie_code = message.text.strip()

    # Logging to check if handler is triggered
    logging.info(f"search_movie_by_code triggered for user: {user_id}, movie_code: {movie_code}")

    if user_id not in user_states:
        logging.error(f"User state not found for user: {user_id}")
        await message.answer("Sizning holatingiz topilmadi. Iltimos, qayta urinib ko'ring.")
        return


    try:
        # Search for the movie in the database
        logging.info(f"Querying movie with code: {movie_code}")
        cursor.execute("SELECT title, year, genre, language, code, video FROM movies WHERE code = ?", (movie_code,))
        movie = cursor.fetchone()
    except Exception as e:
        logging.error(f"Database error: {e}")
        await message.answer("Ma'lumotlar bazasiga ulanishda xatolik. Iltimos, keyinroq qayta urinib ko'ring.")
        return

    # Check if movie was found
    if movie:
        title, year, genre, language, code, video_file_id = movie

        # Prepare movie details for caption
        caption = (
            f"<b>🎬Nomi:</b> {title}\n\n"
            f"<b>📆Yili:</b> {year}\n"
            f"<b>🎞️Janr:</b> {genre}\n"
            f"<b>🌍Tili:</b> {language}\n"
            f"<b>🗂Yuklash:</b> {code}\n\n\n"
            f"<b>🤖Bot:</b> @codermoviebot"
        )


        # Check if video_file_id is not empty or None
        if video_file_id:
            try:
                # Send the video with the caption
                logging.info(f"Sending video to user: {user_id}")
                await bot.send_video(chat_id=user_id, video=video_file_id, caption=caption, parse_mode='HTML')
            except Exception as e:
                logging.error(f"Error sending video: {e}")
                await message.answer("Videoni jo'natishda xatolik yuz berdi.")
        else:
            logging.warning(f"No video file found for movie code: {movie_code}")
            await message.answer("Kino videosi topilmadi.")
    else:
        logging.warning(f"No movie found with code: {movie_code}")
        await message.answer("Kino topilmadi. Iltimos, kodni to'g'ri kiriting yoki qayta urinib ko'ring.")

    # Foydalanuvchi noto'g'ri kod kiritsa, user_states holatini tozalamaymiz
    if movie:
        # Faqat muvaffaqiyatli bo'lsa holatni tozalaymiz
        logging.info(f"Clearing state for user: {user_id}")
        user_states.pop(user_id, None)

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
