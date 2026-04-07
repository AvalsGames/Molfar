import html
import re
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from database.db import AsyncSessionLocal
from models.note import Note
from models.list_item import ListItem
from models.file import FileRecord
from models.chat_history import ChatHistory
from sqlalchemy import select, delete
from utils.ai_client import ai_client

router = Router()

async def get_user_context(user_id: int):
    async with AsyncSessionLocal() as session:
        # Notes
        notes_res = await session.execute(select(Note).where(Note.user_id == user_id).order_by(Note.created_at.desc()).limit(10))
        notes = notes_res.scalars().all()
        
        # Lists
        lists_res = await session.execute(select(ListItem).where(ListItem.user_id == user_id))
        items = lists_res.scalars().all()

        # Files
        files_res = await session.execute(select(FileRecord).where(FileRecord.user_id == user_id).order_by(FileRecord.uploaded_at.desc()))
        files = files_res.scalars().all()

        # History
        hist_res = await session.execute(select(ChatHistory).where(ChatHistory.user_id == user_id).order_by(ChatHistory.created_at.desc()).limit(10))
        history = hist_res.scalars().all()
        history.reverse()
        
    ctx = "ДАНІ КОРИСТУВАЧА:\n"
    if notes:
        ctx += "\n📝 НОТАТКИ:\n" + "\n".join([f"- ID {n.note_id}: {n.content}" for n in notes])
    if items:
        ctx += "\n📋 СПИСКИ:\n" + "\n".join([f"- {i.title} ({i.category}, {i.status})" for i in items])
    if files:
        ctx += "\n📂 ФАЙЛИ:\n" + "\n".join([f"- {f.original_filename} (ID: {f.file_id}, Кат: {f.category}, Теги: {f.tags})" for f in files])
    
    chat = "\n\nІСТОРІЯ РОЗМОВИ:\n" + "\n".join([f"{'Користувач' if h.role=='user' else 'Помічник'}: {h.content}" for h in history])
    return ctx + chat

async def save_chat(user_id: int, role: str, content: str):
    async with AsyncSessionLocal() as session:
        session.add(ChatHistory(user_id=user_id, role=role, content=content))
        await session.commit()

@router.message(F.text == "🤖 Запитати ШІ")
async def ai_menu(message: types.Message):
    await message.answer("Я персональний помічник Мольфар. Я пам'ятаю наші розмови та маю доступ до ваших даних. Запитуйте!")

@router.message(F.text & ~F.text.startswith("/") & ~F.text.startswith("➕") & ~F.text.startswith("📝") & ~F.text.startswith("📋") & ~F.text.startswith("📂") & ~F.text.startswith("⚙️") & ~F.text.startswith("⬅️"))
async def ai_chat_handler(message: types.Message, state: FSMContext):
    # Check if user is in any state (e.g. editing file metadata)
    current_state = await state.get_state()
    if current_state is not None:
        # Let other handlers (like files.py) handle this message
        return
    
    query = message.text
    await save_chat(message.from_user.id, "user", query)
    
    wait_msg = await message.answer("⏳ Мольфар думає...")
    context = await get_user_context(message.from_user.id)
    
    prompt = (
        "Ти - Мольфар, персональний асистент. Твоя мета - допомагати користувачу.\n"
        "1. Використовуй надані ДАНІ КОРИСТУВАЧА та ІСТОРІЮ РОЗМОВИ.\n"
        "2. Якщо користувач просить видалити щось, і ти знаєш ID, додай у відповідь: [DELETE_NOTE:id] або [DELETE_FILE:id].\n"
        "3. Якщо ти згадуєш файл, обов'язково пиши: [FILE_ID:номер].\n"
        "4. Якщо користувач каже 'так' чи 'давай', зрозумій контекст з історії.\n"
        "5. Відповідай українською, будь лаконічним та корисним.\n\n"
        f"{context}\n\nЗАПИТАННЯ: {query}"
    )
    
    response = await ai_client.ask(prompt)
    
    # Process deletions
    note_ids = re.findall(r"\[DELETE_NOTE:(\d+)\]", response)
    file_ids = re.findall(r"\[DELETE_FILE:(\d+)\]", response)
    
    async with AsyncSessionLocal() as session:
        for nid in note_ids: 
            await session.execute(delete(Note).where(Note.note_id == int(nid), Note.user_id == message.from_user.id))
        
        for fid in file_ids:
            # Fetch file record first to get channel_message_id
            f_res = await session.execute(select(FileRecord).where(FileRecord.file_id == int(fid), FileRecord.user_id == message.from_user.id))
            f_rec = f_res.scalar_one_or_none()
            if f_rec:
                from config import FILE_CHANNEL_ID
                import logging
                # Delete from channel
                if FILE_CHANNEL_ID and f_rec.channel_message_id:
                    try:
                        await message.bot.delete_message(chat_id=FILE_CHANNEL_ID, message_id=f_rec.channel_message_id)
                    except Exception as e:
                        logging.error(f"AI deletion: Failed to delete file from channel: {e}")
                
                await session.delete(f_rec)
        
        await session.commit()
    
    clean_res = re.sub(r"\[DELETE_(NOTE|FILE):\d+\]", "", response).strip()
    if note_ids or file_ids: clean_res += "\n\n✅ Виконано: дані видалено з бази."
    
    await save_chat(message.from_user.id, "assistant", clean_res)
    
    # Build file buttons
    found_files = re.findall(r"\[FILE_ID:(\d+)\]", response)
    builder = InlineKeyboardBuilder()
    added = 0
    if found_files:
        async with AsyncSessionLocal() as session:
            for fid in found_files:
                f = await session.get(FileRecord, int(fid))
                if f and f.user_id == message.from_user.id:
                    builder.button(text=f"📥 Скачати {f.original_filename}", callback_data=f"get_{f.file_id}")
                    added += 1
        if added > 0:
            builder.adjust(1)

    await wait_msg.delete()
    await message.answer(clean_res, reply_markup=builder.as_markup() if added > 0 else None)
