import aiosqlite
import re
import sqlite3
import logging
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from config import dp, cursor, conn, user_states, bot, DATABASE_PATH
from utils import (command_start_handler, ensure_subscription, save_previous_state, send_movie_list, send_channel_list,
                   go_back, show_admin_list, save_movie_to_db)
from keyboards import admin_keyboard, only_back_keyboard, bosh_sahifa_keyboard
from commands import admin_panel_handler


# Handlers
@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        await conn.execute("INSERT OR IGNORE INTO users (telegram_id) VALUES (?)", (user_id,))
        await conn.commit()

    if not await ensure_subscription(message):
        return  # Stop further execution if the user is not subscribed

    await command_start_handler(message)

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
