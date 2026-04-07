from aiogram import Router, types, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from database.db import AsyncSessionLocal
from models.reminder import Reminder
from utils.scheduler import scheduler
from utils.helpers import validate_date_format
from datetime import datetime
import pytz
from config import DEFAULT_TIMEZONE
from sqlalchemy import select, delete

router = Router()

class ReminderStates(StatesGroup):
    waiting_for_remind_data = State()

async def send_reminder_job(bot: Bot, user_id: int, reminder_text: str, reminder_id: int):
    try:
        await bot.send_message(user_id, f"⏰ **Нагадування!**\n\n{reminder_text}", parse_mode="Markdown")
        
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(Reminder).where(Reminder.reminder_id == reminder_id, Reminder.is_recurring == False)
            )
            await session.commit()
    except Exception as e:
        print(f"Error sending reminder: {e}")

@router.message(F.text == "⏰ Нагадування")
@router.message(Command("reminders"))
async def list_reminders(message: types.Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Reminder).where(
                Reminder.user_id == message.from_user.id,
                Reminder.is_active == True
            ).order_by(Reminder.scheduled_time)
        )
        reminders = result.scalars().all()

    text = "⏰ **Ваші активні нагадування:**\n\n"
    if not reminders:
        text += "У вас немає активних нагадувань."
    else:
        for r in reminders:
            text += f"🆔 {r.reminder_id} | {r.scheduled_time.strftime('%Y-%m-%d %H:%M')}\n📝 {r.text}\n\n"
    
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="➕ Додати нагадування"))
    builder.row(types.KeyboardButton(text="⬅️ Назад до меню"))
    
    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup(resize_keyboard=True))

@router.message(F.text == "➕ Додати нагадування")
async def start_add_reminder(message: types.Message, state: FSMContext):
    await state.set_state(ReminderStates.waiting_for_remind_data)
    await message.answer(
        "Введіть нагадування у форматі:\n`РРРР-ММ-ДД ГГ:ХХ Текст`\n\nПриклад:\n`2025-04-15 14:30 Купити молоко`",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.message(ReminderStates.waiting_for_remind_data)
async def process_add_reminder(message: types.Message, state: FSMContext, bot: Bot):
    try:
        parts = message.text.split(" ", 2)
        if len(parts) < 3:
            raise ValueError
        
        date_str = f"{parts[0]} {parts[1]}"
        reminder_text = parts[2]
        
        tz = pytz.timezone(DEFAULT_TIMEZONE)
        scheduled_time = tz.localize(datetime.strptime(date_str, "%Y-%m-%d %H:%M"))
        
        if scheduled_time < datetime.now(tz):
            await message.answer("❌ Час уже минув. Виберіть майбутню дату.")
            return

        async with AsyncSessionLocal() as session:
            new_reminder = Reminder(
                user_id=message.from_user.id,
                text=reminder_text,
                scheduled_time=scheduled_time.replace(tzinfo=None),
                is_active=True
            )
            session.add(new_reminder)
            await session.commit()
            await session.refresh(new_reminder)
        
        scheduler.add_job(
            send_reminder_job,
            'date',
            run_date=scheduled_time,
            args=[bot, message.from_user.id, reminder_text, new_reminder.reminder_id],
            id=f"reminder_{new_reminder.reminder_id}"
        )
        
        await state.clear()
        await message.answer(f"✅ Нагадування встановлено!")
        await list_reminders(message)

    except ValueError:
        await message.answer("❌ Невірний формат. Спробуйте ще раз:\n`РРРР-ММ-ДД ГГ:ХХ Текст`", parse_mode="Markdown")

@router.message(Command("remind"))
async def add_reminder_cmd(message: types.Message, command: CommandObject, bot: Bot):
    # Keep command support but call the logic
    if not command.args:
        await start_add_reminder(message, None)
        return
    # ... rest of logic if needed, but easier to just use the state flow

@router.message(Command("delete_reminder"))
async def delete_reminder_cmd(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Використовуйте: /delete_reminder <ID>")
        return

    try:
        reminder_id = int(command.args)
    except ValueError:
        await message.answer("Невірний ID напоминання.")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(Reminder).where(
                Reminder.reminder_id == reminder_id,
                Reminder.user_id == message.from_user.id
            )
        )
        await session.commit()
        
        if result.rowcount > 0:
            # Try to remove from scheduler if exists
            try:
                scheduler.remove_job(f"reminder_{reminder_id}")
            except:
                pass
            await message.answer(f"✅ Напоминання {reminder_id} видалено.")
        else:
            await message.answer(f"❌ Напоминання {reminder_id} не знайдено.")
