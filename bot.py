import sqlite3
import asyncio
import aiohttp
import logging
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

cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY,
        telegram_id TEXT UNIQUE
    )
''')

cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id TEXT UNIQUE
        )
    ''')

# Create necessary tables
cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY,
            telegram_id TEXT UNIQUE
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
    video TEXT  -- Storing the video file_id as TEXT
);

    ''')

conn.commit()

# User state management
user_states = {}

# Track previous states for back functionality
previous_states = {}


# Utility functions
async def check_subscription(user_id):
    cursor.execute("SELECT telegram_id FROM channels")
    channels = cursor.fetchall()
    logging.info(f"Checking subscription for user_id={user_id} against channels={channels}")

    for channel in channels:
        try:
            chat_member = await bot.get_chat_member(chat_id=channel[0], user_id=user_id)
            logging.info(f"Channel: {channel[0]}, Status: {chat_member.status}")
            if chat_member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            logging.error(f"Error checking subscription for channel {channel[0]}: {e}")
            return False

    return True




def get_inline_keyboard_for_channels():
    cursor.execute("SELECT telegram_id FROM channels")
    channels = cursor.fetchall()

    inline_keyboard = [
        [InlineKeyboardButton(text=f"{channel[0]}", url=f'https://t.me/{channel[0].lstrip("@")}')]
        for channel in channels
    ]
    inline_keyboard.append([InlineKeyboardButton(text="A'zo bo'ldim", callback_data='azo')])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)



def admin_keyboard():
    buttons = [
        [KeyboardButton(text="➕ Kino qo'shish"), KeyboardButton(text="❌ Kino o'chirish")],
        [KeyboardButton(text="➕ Kanal qo'shish"), KeyboardButton(text="❌ Kanal o'chirish")],
        [KeyboardButton(text="👥Foydalanuvchilarga xabar yuborish")],
        [KeyboardButton(text="➕ Admin qo'shish"), KeyboardButton(text="❌ Admin o'chirish")],
        [KeyboardButton(text="🏠 Bosh menyu")]  # Bosh menyu button
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)




@dp.message(lambda message: message.text == "🏠 Bosh menyu")
async def handle_bosh_menyu(message: Message):
    await command_start_handler(message)  # Direct the user to the main menu


def only_back_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Orqaga")]], resize_keyboard=True)


async def download_video(file_id):
    file = await bot.get_file(file_id)
    download_url = f'https://api.telegram.org/file/bot{TOKEN}/{file.file_path}'

    async with aiohttp.ClientSession() as session:
        async with session.get(download_url) as resp:
            if resp.status == 200:
                file_data = await resp.read()
                return file_data
            else:
                logging.error(f"Failed to download video. HTTP Status: {resp.status}")
                return None



async def handle_video_upload(message):
    video = message.video
    if video and video.mime_type == 'video/mp4':
        logging.info(f"Received video with MIME type: {video.mime_type}")
        video_data = await download_video(video.file_id)
        if video_data:
            return video_data
        else:
            await message.answer("Videoni yuklab olishda xatolik yuz berdi.")
    else:
        logging.warning(f"Received file is not a valid MP4 video. MIME type: {video.mime_type}")
        await message.answer("Fayl MP4 formatida bo'lishi kerak. Iltimos, qaytadan yuboring.")
    return None


async def save_movie_to_db(user_id):
    try:
        cursor.execute('''
            INSERT INTO movies (code, title, year, genre, language, video) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_states[user_id]['code'],
            user_states[user_id]['title'],
            user_states[user_id]['year'],
            user_states[user_id]['genre'],
            user_states[user_id]['language'],
            user_states[user_id]['video_file_id']  # Save the file_id, not the video data itself
        ))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error saving movie to database: {e}")
        return False



# Handlers
@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id

    # Store user ID in the database if it's not already there
    cursor.execute("INSERT OR IGNORE INTO users (telegram_id) VALUES (?)", (user_id,))
    conn.commit()

    if await check_subscription(user_id):
        await command_start_handler(message)
    else:
        await send_subscription_prompt(message)


async def send_subscription_prompt(message: Message):
    inline_keyboard = get_inline_keyboard_for_channels()
    await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=inline_keyboard)


@dp.callback_query(lambda c: c.data == 'azo')
async def callback_handler(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await check_subscription(user_id):
        await command_start_handler(callback_query.message)
    else:
        await send_subscription_prompt(callback_query.message)



async def command_start_handler(message: Message):
    user_id = message.from_user.id

    # Check if the user is an admin
    cursor.execute("SELECT telegram_id FROM admins WHERE telegram_id = ?", (user_id,))
    admin = cursor.fetchone()

    admin_button = [KeyboardButton(text="🛠 Admin panel")] if admin else []

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Kino qidirish")],
            [KeyboardButton(text="🤖Telegram bot yasatish")],
            admin_button
        ],
        resize_keyboard=True
    )
    user_name = message.from_user.first_name or "foydalanuvchi"

    await message.answer(
        f"<b>👋Salom  {user_name}</b>\n\n <i>Kod orqali kinoni topishingiz mumkin!</i>",
        reply_markup=keyboard, parse_mode='html'
    )


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
    user_id = message.from_user.id
    user_states[user_id] = {'state': 'searching_movie'}
    await message.answer("<i>Kino kodini yuboring...</i>", reply_markup=only_back_keyboard(), parse_mode='html')
@dp.message(lambda message: message.text == "🤖Telegram bot yasatish")
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
    user_states[message.from_user.id] = 'add_channel'
    await message.answer("Kanal username'ini yuboring (masalan: @example_channel).", reply_markup=only_back_keyboard())


@dp.message(lambda message: message.text == "❌ Kanal o'chirish")
async def delete_channel_request(message: Message):
    save_previous_state(message.from_user.id, 'admin_panel')
    user_states[message.from_user.id] = 'delete_channel'
    await send_channel_list(message)


@dp.message(lambda message: message.text == "🔙 Orqaga")
async def handle_back_button(message: Message):
    user_id = message.from_user.id
    await go_back(user_id, message)


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


@dp.callback_query(lambda c: c.data and c.data.startswith("delete_"))
async def handle_channel_deletion(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    channel_username = callback_query.data[len("delete_"):].strip()

    # Kanalni o'chirish
    try:
        cursor.execute("DELETE FROM channels WHERE telegram_id = ?", (channel_username,))
        conn.commit()
        await callback_query.message.answer("Kanal muvaffaqiyatli o'chirildi.", reply_markup=admin_keyboard())
    except Exception as e:
        await callback_query.message.answer(f"Xatolik yuz berdi: {e}", reply_markup=admin_keyboard())

    # CallbackQuery'dan foydalanib xabarni o'chirish
    await callback_query.message.delete()


@dp.message(lambda message: user_states.get(message.from_user.id) == 'add_channel')
async def handle_channel_username(message: Message):
    user_id = message.from_user.id
    username = message.text.strip()

    # Username to'g'ri formatda ekanligini tekshirish
    if re.match(r'^@\w+$', username):
        # Kanalni ma'lumotlar bazasiga qo'shish
        try:
            cursor.execute("INSERT INTO channels (telegram_id) VALUES (?)", (username,))
            conn.commit()
            await message.answer("Kanal muvaffaqiyatli qo'shildi!", reply_markup=admin_keyboard())
        except sqlite3.IntegrityError:
            await message.answer("Bu kanal username allaqachon mavjud!", reply_markup=admin_keyboard())
        except Exception as e:
            await message.answer(f"Xatolik yuz berdi: {e}", reply_markup=admin_keyboard())
    else:
        await message.answer("Iltimos, to'g'ri formatda kanal username'ini kiriting (masalan: @example_channel).",
                             reply_markup=only_back_keyboard())


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
    await go_back(user_id, message)
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
        await go_back(user_id, message)
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
            await go_back(user_id, message)
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
        cursor.execute("SELECT title, year, genre, language, video FROM movies WHERE code = ?", (movie_code,))
        movie = cursor.fetchone()
    except Exception as e:
        logging.error(f"Database error: {e}")
        await message.answer("Ma'lumotlar bazasiga ulanishda xatolik. Iltimos, keyinroq qayta urinib ko'ring.")
        return

    # Check if movie was found
    if movie:
        title, year, genre, language, video_file_id = movie

        # Prepare movie details for caption
        caption = (
            f"<b>Nomi:</b> {title}\n"
            f"<b>Yili:</b> {year}\n"
            f"<b>Janr:</b> {genre}\n"
            f"<b>Tili:</b> {language}"
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
