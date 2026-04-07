from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import AsyncSessionLocal
from models.note import Note
from sqlalchemy import select, delete, or_

router = Router()

class NoteStates(StatesGroup):
    waiting_for_note_text = State()
    waiting_for_edit_text = State()

@router.message(F.text == "➕ Нова нотатка")
async def start_new_note(message: types.Message, state: FSMContext):
    await message.answer("Введіть текст нової нотатки:")
    await state.set_state(NoteStates.waiting_for_note_text)

@router.message(NoteStates.waiting_for_note_text)
async def process_new_note(message: types.Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        new_note = Note(user_id=message.from_user.id, content=message.text)
        session.add(new_note)
        await session.commit()
        await session.refresh(new_note)
    
    await message.answer(f"✅ Нотатка збережена (ID: {new_note.note_id})!")
    await state.clear()

@router.message(F.text == "📝 Мої нотатки")
@router.message(Command("notes"))
async def list_notes(message: types.Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Note).where(Note.user_id == message.from_user.id).order_by(Note.created_at.desc())
        )
        notes = result.scalars().all()

    if not notes:
        await message.answer("📁 Ваша скринька нотаток порожня.")
        return

    for note in notes[:15]:
        builder = InlineKeyboardBuilder()
        # Весь текст нотатки стає кнопкою
        builder.button(text=f"📝 {note.content}", callback_data=f"ndel_{note.note_id}")
        await message.answer(f"Нотатка:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("ndel_"))
async def delete_note_callback(callback: types.CallbackQuery):
    note_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Note).where(Note.note_id == note_id, Note.user_id == callback.from_user.id))
        note = res.scalar_one_or_none()
        
        if note:
            await session.delete(note)
            await session.commit()
            await callback.answer("✅ Видалено")
            await callback.message.delete()
        else:
            await callback.answer("❌ Вже видалено")

@router.message(Command("delete_note"))
async def delete_note_cmd(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Будь ласка, вкажіть ID нотатки: /delete_note <ID>")
        return

    try:
        note_id = int(command.args)
    except ValueError:
        await message.answer("Невірний ID нотатки.")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(Note).where(Note.note_id == note_id, Note.user_id == message.from_user.id)
        )
        await session.commit()
        
        if result.rowcount > 0:
            await message.answer(f"✅ Нотатка {note_id} видалена.")
        else:
            await message.answer(f"❌ Нотатка {note_id} не знайдена.")

@router.message(Command("search"))
@router.message(F.text.startswith("/search"))
async def search_notes(message: types.Message, command: CommandObject):
    query = command.args if command.args else message.text.replace("/search", "").strip()
    if not query:
        await message.answer("Будь ласка, вкажіть ключове слово для пошуку: /search <ключове слово>")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Note).where(
                Note.user_id == message.from_user.id,
                Note.content.ilike(f"%{query}%")
            ).order_by(Note.created_at.desc())
        )
        notes = result.scalars().all()

    if not notes:
        await message.answer(f"Нічого не знайдено за запитом: {query}")
        return

    for note in notes[:10]:
        builder = InlineKeyboardBuilder()
        builder.button(text=f"📝 {note.content}", callback_data=f"ndel_{note.note_id}")
        await message.answer(f"Знайдена нотатка:", reply_markup=builder.as_markup())
