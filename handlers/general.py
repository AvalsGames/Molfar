from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from database.db import AsyncSessionLocal
from models.user import User
from sqlalchemy import select
from sqlalchemy.orm import selectinload

router = Router()

def get_main_menu_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="➕ Нова нотатка"), types.KeyboardButton(text="📝 Мої нотатки"))
    builder.row(types.KeyboardButton(text="📋 Мої списки"), types.KeyboardButton(text="📂 Файли"))
    builder.row(types.KeyboardButton(text="🤖 Запитати ШІ"), types.KeyboardButton(text="⚙️ Налаштування"))
    return builder.as_markup(resize_keyboard=True)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    async with AsyncSessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(user_id=message.from_user.id, username=message.from_user.username)
            session.add(user)
            await session.commit()
    
    await message.answer(
        "Привіт! Я твій особистий помічник. Я допоможу тобі керувати нотатками, списками та відповідатиму на твої запитання за допомогою ШІ.",
        reply_markup=get_main_menu_keyboard()
    )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "📚 **Доступні команди:**\n\n"
        "**📝 Нотатки:**\n"
        "/note <текст> - Додати нотатку\n"
        "/notes - Переглянути всі нотатки\n"
        "/delete_note <id> - Видалити нотатку\n"
        "/search <текст> - Пошук по нотатках\n\n"
        "**📋 Списки:**\n"
        "/add_to_list <категорія> <назва> - Додати до списку\n"
        "/list <категорія> - Переглянути список\n\n"
        "**🤖 ШІ:**\n"
        "Просто пишіть мені будь-що без команд для спілкування з ШІ!\n\n"
        "**📂 Файли:**\n"
        "/files - Список завантажених файлів\n\n"
        "Використовуйте кнопки меню для швидкого доступу!"
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.message(Command("settings"))
@router.message(F.text == "⚙️ Налаштування")
async def cmd_settings(message: types.Message):
    async with AsyncSessionLocal() as session:
        user = await session.get(User, message.from_user.id)
    
    settings_text = (
        f"⚙️ **Ваші налаштування:**\n\n"
        f"👤 ID: `{user.user_id}`\n"
        f"🌍 Часовий пояс: `{user.timezone}`\n"
        f"📅 Дата реєстрації: {user.created_at.strftime('%Y-%m-%d')}\n\n"
        "Для зміни часового поясу (незабаром) використовуйте /timezone."
    )
    await message.answer(settings_text, parse_mode="Markdown")

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    from models.note import Note
    from models.list_item import ListItem
    from models.reminder import Reminder
    from models.file import FileRecord
    from sqlalchemy import func

    async with AsyncSessionLocal() as session:
        notes_count = await session.scalar(select(func.count(Note.note_id)).where(Note.user_id == message.from_user.id))
        items_count = await session.scalar(select(func.count(ListItem.item_id)).where(ListItem.user_id == message.from_user.id))
        reminders_count = await session.scalar(select(func.count(Reminder.reminder_id)).where(Reminder.user_id == message.from_user.id))
        files_count = await session.scalar(select(func.count(FileRecord.file_id)).where(FileRecord.user_id == message.from_user.id))

    stats_text = (
        f"📊 **Ваша статистика:**\n"
        f"📝 Нотатки: {notes_count}\n"
        f"📋 Елементи в списках: {items_count}\n"
        f"⏰ Нагадування: {reminders_count}\n"
        f"📂 Файли: {files_count}"
    )
    await message.answer(stats_text, parse_mode="Markdown")
