from aiogram import Router, types, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import AsyncSessionLocal
from models.file import FileRecord
import logging
import hashlib
from config import FILE_CHANNEL_ID
from sqlalchemy import select, delete, func
from utils.ai_client import ai_client

router = Router()

class FileStates(StatesGroup):
    waiting_for_approval = State()
    editing_category = State()
    editing_tags = State()

def get_cat_hash(name):
    # Create a short hash for callback_data to avoid BUTTON_DATA_INVALID
    return hashlib.md5(name.encode()).hexdigest()[:8]

@router.message(F.text == "📂 Файли")
@router.message(Command("files"))
async def files_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(FileRecord.category, func.count(FileRecord.file_id))
            .where(FileRecord.user_id == message.from_user.id)
            .group_by(FileRecord.category)
        )
        categories = result.all()

    if not categories:
        await message.answer("📁 Ваше сховище порожнє. Просто надішліть файл, щоб почати!")
        return

    builder = InlineKeyboardBuilder()
    for cat_name, count in categories:
        display_name = cat_name if cat_name and cat_name != "None" else "Загальне"
        
        # callback_data max 64 BYTES. Ukrainian chars take 2 bytes.
        cb_prefix = "fcat_"
        full_cb = f"{cb_prefix}{cat_name}"
        
        if len(full_cb.encode('utf-8')) > 64:
            cb_data = f"hcat_{get_cat_hash(cat_name)}"
        else:
            cb_data = full_cb
            
        # Also truncate display name if it's way too long for a button
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
            
        builder.button(text=f"📁 {display_name} ({count})", callback_data=cb_data)
    
    builder.button(text="🔍 Пошук за назвою", callback_data="fsearch_start")
    builder.adjust(1)

    text = "📂 <b>Хмарне сховище:</b>\nОберіть категорію або скористайтеся пошуком:"
    
    if isinstance(message, types.CallbackQuery):
        await message.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("fcat_"))
@router.callback_query(F.data.startswith("hcat_"))
async def list_files_in_category(callback: types.CallbackQuery):
    cb_data = callback.data
    async with AsyncSessionLocal() as session:
        if cb_data.startswith("hcat_"):
            # If it's a hash, we need to find which category it belongs to
            h = cb_data.replace("hcat_", "")
            result = await session.execute(select(FileRecord.category).where(FileRecord.user_id == callback.from_user.id).group_by(FileRecord.category))
            all_cats = result.scalars().all()
            category = next((c for c in all_cats if get_cat_hash(c) == h), "Загальне")
        else:
            category = cb_data.replace("fcat_", "")

        result = await session.execute(
            select(FileRecord)
            .where(FileRecord.user_id == callback.from_user.id, FileRecord.category == category)
            .order_by(FileRecord.uploaded_at.desc())
        )
        files = result.scalars().all()

    if not files:
        await callback.answer("Файли не знайдені.")
        return

    # Delete previous message to keep chat clean
    try:
        await callback.message.delete()
    except: pass

    await callback.message.answer(f"📁 <b>Категорія: {category}</b>", parse_mode="HTML")
    
    for f in files:
        tags_str = f"\n🏷 <code>{f.tags}</code>" if f.tags else ""
        text = f"📄 <b>{f.original_filename}</b>{tags_str}"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📥 Скачати", callback_data=f"get_{f.file_id}")
        builder.button(text="🗑 Видалити", callback_data=f"fdel_{f.file_id}")
        builder.adjust(2)
        
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    
    # Add a back button
    back_builder = InlineKeyboardBuilder()
    back_builder.button(text="⬅️ Назад до категорій", callback_data="fmenu_back")
    await callback.message.answer("Повернутися до списку категорій:", reply_markup=back_builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "fmenu_back")
async def back_to_categories(callback: types.CallbackQuery, state: FSMContext):
    try:
        # Try to delete multiple messages if possible, but at least the last one
        await callback.message.delete()
    except: pass
    await files_main_menu(callback, state)
    await callback.answer()

@router.callback_query(F.data == "fsearch_start")
async def start_file_search(callback: types.CallbackQuery):
    await callback.message.answer("🔎 Напишіть назву файлу або ключове слово для пошуку:")
    await callback.answer()

@router.callback_query(F.data.startswith("get_"))
async def get_file_callback(callback: types.CallbackQuery, bot: Bot):
    file_id_db = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(FileRecord).where(FileRecord.file_id == file_id_db, FileRecord.user_id == callback.from_user.id)
        )
        file_record = result.scalar_one_or_none()
        
    if not file_record:
        await callback.answer("❌ Файл не знайдено.")
        return

    await callback.answer("⏳ Готую файл...")
    try:
        if file_record.file_type == "photo":
            await bot.send_photo(callback.from_user.id, file_record.file_tg_id, caption=file_record.original_filename)
        elif file_record.file_type == "audio":
            await bot.send_audio(callback.from_user.id, file_record.file_tg_id, caption=file_record.original_filename)
        elif file_record.file_type == "video":
            await bot.send_video(callback.from_user.id, file_record.file_tg_id, caption=file_record.original_filename)
        else:
            await bot.send_document(callback.from_user.id, file_record.file_tg_id, caption=file_record.original_filename)
    except Exception as e:
        await callback.message.answer(f"❌ Помилка: {str(e)}")

@router.callback_query(F.data.startswith("fdel_"))
async def delete_file_callback(callback: types.CallbackQuery, bot: Bot):
    file_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(FileRecord).where(FileRecord.user_id == callback.from_user.id, FileRecord.file_id == file_id)
        )
        file_record = result.scalar_one_or_none()
        
        if file_record:
            # Delete from channel if message_id exists
            if FILE_CHANNEL_ID and file_record.channel_message_id:
                try:
                    await bot.delete_message(chat_id=FILE_CHANNEL_ID, message_id=file_record.channel_message_id)
                except Exception as e:
                    logging.error(f"Failed to delete file from channel: {e}")
            
            await session.delete(file_record)
            await session.commit()
            await callback.answer("✅ Видалено всюди")
            await callback.message.delete()
        else:
            await callback.answer("❌ Файл вже видалено")

@router.message(F.document | F.photo | F.audio | F.video)
async def handle_file_upload(message: types.Message, bot: Bot, state: FSMContext):
    file_type, file_id, file_name = "", "", ""
    
    if message.document:
        file_type, file_id, file_name = "document", message.document.file_id, message.document.file_name or "file"
    elif message.photo:
        file_type, file_id, file_name = "photo", message.photo[-1].file_id, f"photo_{message.photo[-1].file_unique_id}.jpg"
    elif message.audio:
        file_type, file_id, file_name = "audio", message.audio.file_id, message.audio.file_name or "audio"
    elif message.video:
        file_type, file_id, file_name = "video", message.video.file_id, "video.mp4"

    if not file_id: return

    msg_wait = await message.answer("⏳ Мольфар аналізує файл...")

    # Forward to channel
    channel_msg_id = None
    if FILE_CHANNEL_ID:
        try:
            fwd = await bot.copy_message(chat_id=FILE_CHANNEL_ID, from_chat_id=message.chat.id, message_id=message.message_id)
            channel_msg_id = fwd.message_id
        except Exception as e:
            logging.error(f"Channel forward failed: {e}")

    # Hardcoded category logic based on extension and type
    detected_category = "Загальне"
    ext = file_name.split('.')[-1].lower() if '.' in file_name else ""
    
    if file_type == "photo" or ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
        detected_category = "Зображення"
    elif file_type == "video" or ext in ['mp4', 'mov', 'avi', 'mkv', 'wmv']:
        detected_category = "Відео"
    elif file_type == "audio" or ext in ['mp3', 'wav', 'ogg', 'm4a', 'flac']:
        detected_category = "Аудіо"
    elif ext in ['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt']:
        detected_category = "Документи"
    elif ext in ['zip', 'rar', '7z', 'tar', 'gz']:
        detected_category = "Архіви"

    # AI Analysis
    ai_category, ai_tags = detected_category, ""
    try:
        prompt = (
            f"Проаналізуй файл. Назва: '{file_name}', Тип: '{file_type}', Технічна категорія: '{detected_category}'.\n"
            f"Запропонуй найкращу категорію (одне слово) та 2-3 теги.\n"
            f"ПИШИ ТІЛЬКИ РЕЗУЛЬТАТ У ФОРМАТІ: НазваКатегорії | Тег1, Тег2\n"
            f"НЕ ПИШИ слів 'Категорія:', 'Теги:' чи будь-яких пояснень.\n"
            f"Якщо це зображення, категорія МАЄ БУТИ 'Зображення'.\n"
            f"Мова: українська."
        )
        res = await ai_client.ask(prompt)
        
        # Robust parsing
        if "|" in res:
            # If AI returned multiple lines, take the one with the pipe
            lines = [l.strip() for l in res.split('\n') if '|' in l]
            target_line = lines[0] if lines else res.split('\n')[0]
            
            parts = target_line.split("|", 1)
            new_cat = parts[0].strip()
            new_tags = parts[1].strip()
            
            # Clean up AI prefixes like "Категорія: Зображення" -> "Зображення"
            def clean_ai_text(text):
                text = text.replace("**", "").replace("*", "").replace("`", "")
                prefixes = ["Категорія:", "Категорія", "Category:", "Теги:", "Теги", "Tags:"]
                for p in prefixes:
                    if text.startswith(p):
                        text = text[len(p):].strip()
                return text

            new_cat = clean_ai_text(new_cat)
            new_tags = clean_ai_text(new_tags)
            
            if new_cat and new_cat.lower() not in ["категорія", "загальне"]:
                ai_category = new_cat
            ai_tags = new_tags
    except: pass

    await state.update_data(
        file_tg_id=file_id, file_type=file_type, file_name=file_name,
        channel_msg_id=channel_msg_id, category=ai_category, tags=ai_tags,
        main_msg_id=msg_wait.message_id
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Затвердити", callback_data="fapp_confirm")
    builder.button(text="✏️ Змінити категорію", callback_data="fapp_edit_cat")
    builder.button(text="🏷 Змінити теги", callback_data="fapp_edit_tags")
    builder.adjust(1)

    await msg_wait.edit_text(
        f"🤖 <b>ШІ пропонує:</b>\n\n"
        f"📄 Назва: <code>{file_name}</code>\n"
        f"📂 Категорія: <code>{ai_category}</code>\n"
        f"🏷 Теги: <code>{ai_tags}</code>\n\n"
        f"Бажаєте затвердити чи змінити?",
        parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await state.set_state(FileStates.waiting_for_approval)

@router.callback_query(FileStates.waiting_for_approval, F.data == "fapp_confirm")
async def confirm_file_upload(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        new_file = FileRecord(
            user_id=callback.from_user.id, original_filename=data['file_name'],
            file_type=data['file_type'], file_tg_id=data['file_tg_id'],
            channel_message_id=data['channel_msg_id'], category=data['category'], tags=data['tags']
        )
        session.add(new_file)
        await session.commit()
    
    await callback.message.edit_text(f"✅ Файл <b>{data['file_name']}</b> збережено у категорію <b>{data['category']}</b>!", parse_mode="HTML")
    await state.clear()
    await callback.answer()

@router.callback_query(FileStates.waiting_for_approval, F.data == "fapp_edit_cat")
async def edit_file_category(callback: types.CallbackQuery, state: FSMContext):
    msg = await callback.message.answer("Введіть нову назву категорії (одне слово):")
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(FileStates.editing_category)
    await callback.answer()

@router.message(FileStates.editing_category)
async def process_edit_category(message: types.Message, state: FSMContext, bot: Bot):
    new_cat = message.text.strip()
    data = await state.get_data()
    
    # Clean up user message and our prompt
    try:
        await message.delete()
        if 'last_msg_id' in data:
            await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass

    await state.update_data(category=new_cat)
    await show_current_file_status(message, state)

@router.callback_query(FileStates.waiting_for_approval, F.data == "fapp_edit_tags")
async def edit_file_tags(callback: types.CallbackQuery, state: FSMContext):
    msg = await callback.message.answer("Введіть нові теги через кому:")
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(FileStates.editing_tags)
    await callback.answer()

@router.message(FileStates.editing_tags)
async def process_edit_tags(message: types.Message, state: FSMContext, bot: Bot):
    new_tags = message.text.strip()
    data = await state.get_data()

    # Clean up user message and our prompt
    try:
        await message.delete()
        if 'last_msg_id' in data:
            await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass

    await state.update_data(tags=new_tags)
    await show_current_file_status(message, state)

async def show_current_file_status(message: types.Message, state: FSMContext):
    data = await state.get_data()
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Затвердити", callback_data="fapp_confirm")
    builder.button(text="✏️ Змінити категорію", callback_data="fapp_edit_cat")
    builder.button(text="🏷 Змінити теги", callback_data="fapp_edit_tags")
    builder.adjust(1)

    # Use edit_text if we have a message_id to edit, otherwise send new
    text = (
        f"📝 <b>Поточні дані файлу:</b>\n\n"
        f"📄 Назва: <code>{data['file_name']}</code>\n"
        f"📂 Категорія: <code>{data.get('category', 'Загальне')}</code>\n"
        f"🏷 Теги: <code>{data.get('tags', '')}</code>\n\n"
        f"Затвердити чи змінити ще щось?"
    )

    if 'main_msg_id' in data:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=data['main_msg_id'],
                text=text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        except:
            msg = await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
            await state.update_data(main_msg_id=msg.message_id)
    else:
        msg = await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
        await state.update_data(main_msg_id=msg.message_id)
    
    await state.set_state(FileStates.waiting_for_approval)
