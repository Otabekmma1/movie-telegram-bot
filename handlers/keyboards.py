from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


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
