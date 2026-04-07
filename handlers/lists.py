from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import AsyncSessionLocal
from models.list_item import ListItem
from sqlalchemy import select, update, delete

router = Router()

CATEGORIES = ["🎬 Фільми", "📺 Серіали", "🎮 Ігри", "📺 Аніме"]
STATUSES = {
    'до_перегляду': '⏳ До перегляду',
    'переглядаю': '👀 Переглядаю',
    'переглянув': '✅ Переглянув'
}

class ListStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_title = State()

def get_list_categories_keyboard(with_back=False):
    builder = ReplyKeyboardBuilder()
    for cat in CATEGORIES:
        builder.add(types.KeyboardButton(text=cat))
    builder.adjust(2)
    if with_back:
        builder.row(types.KeyboardButton(text="⬅️ Назад до меню"))
    return builder.as_markup(resize_keyboard=True)

@router.message(F.text == "📋 Мої списки")
@router.message(F.text == "⬅️ Назад до списків")
async def show_list_categories(message: types.Message, state: FSMContext):
    await state.clear()
    
    # Cleanup old categories from DB (optional, but requested "other can be deleted")
    # We will do it once when the user opens the menu
    async with AsyncSessionLocal() as session:
        # Convert category names to plain text for comparison if needed, 
        # but here we use the exact strings from CATEGORIES
        await session.execute(
            delete(ListItem).where(
                ListItem.user_id == message.from_user.id,
                ListItem.category.not_in(CATEGORIES)
            )
        )
        await session.commit()

    await message.answer("Оберіть категорію для перегляду або керування:", reply_markup=get_list_categories_keyboard(with_back=True))

@router.message(F.text == "⬅️ Назад до меню")
async def back_to_main_menu(message: types.Message):
    from handlers.general import get_main_menu_keyboard
    await message.answer("Головне меню:", reply_markup=get_main_menu_keyboard())

@router.message(F.text.in_(CATEGORIES))
async def list_items_by_category(message: types.Message):
    category = message.text
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ListItem).where(
                ListItem.user_id == message.from_user.id,
                ListItem.category == category
            ).order_by(ListItem.added_at.desc())
        )
        items = result.scalars().all()

    text = f"{category} **Ваш список:**\n\n"
    if not items:
        text += "У цій категорії ще немає елементів."
    else:
        text += "Натисніть на пункт, щоб видалити його зі списку:"
    
    builder = InlineKeyboardBuilder()
    if items:
        for item in items:
            builder.button(text=f"📍 {item.title}", callback_data=f"del_{item.item_id}")
    
    builder.adjust(1)
    
    reply_builder = ReplyKeyboardBuilder()
    reply_builder.row(types.KeyboardButton(text=f"➕ Додати в {category}"))
    reply_builder.row(types.KeyboardButton(text="⬅️ Назад до списків"))
    
    await message.answer(text, parse_mode="Markdown", reply_markup=reply_builder.as_markup(resize_keyboard=True))
    if items:
        await message.answer("Список елементів (натисніть для видалення):", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("del_"))
async def delete_list_item_callback(callback: types.CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        # Get item to know its category for refresh
        item_res = await session.execute(select(ListItem).where(ListItem.item_id == item_id))
        item = item_res.scalar_one_or_none()
        
        if not item:
            await callback.answer("❌ Елемент вже видалено")
            return
            
        category = item.category
        await session.delete(item)
        await session.commit()
        
        await callback.answer("✅ Видалено")
        
        # Refresh the list view
        result = await session.execute(
            select(ListItem).where(
                ListItem.user_id == callback.from_user.id,
                ListItem.category == category
            ).order_by(ListItem.added_at.desc())
        )
        items = result.scalars().all()

        text = f"{category} **Ваш список:**\n\n"
        if not items:
            text += "У цій категорії ще немає елементів."
        else:
            text += "Натисніть на пункт, щоб видалити його зі списку:"
        
        builder = InlineKeyboardBuilder()
        for i in items:
            builder.button(text=f"📍 {i.title}", callback_data=f"del_{i.item_id}")
        builder.adjust(1)
        
        try:
            await callback.message.edit_text(text, parse_mode="Markdown")
            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        except:
            # If message content didn't change, just answer
            pass

@router.message(F.text.startswith("➕ Додати в "))
async def start_add_to_list(message: types.Message, state: FSMContext):
    category = message.text.replace("➕ Додати в ", "").strip()
    if category not in CATEGORIES:
        await message.answer("Помилка категорії.")
        return
    
    await state.update_data(category=category)
    await state.set_state(ListStates.waiting_for_title)
    await message.answer(f"Введіть назву для категорії {category}:", reply_markup=types.ReplyKeyboardRemove())

@router.message(ListStates.waiting_for_title)
async def process_add_to_list(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get('category')
    title = message.text.strip()

    async with AsyncSessionLocal() as session:
        new_item = ListItem(user_id=message.from_user.id, category=category, title=title)
        session.add(new_item)
        await session.commit()
        await session.refresh(new_item)
    
    await state.clear()
    
    # Return to category view
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text=f"➕ Додати в {category}"))
    builder.row(types.KeyboardButton(text="⬅️ Назад до списків"))
    
    await message.answer(
        f"✅ '{title}' додано до категорії {category}!",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    # Trigger list refresh
    message.text = category
    await list_items_by_category(message)

@router.message(Command("add_to_list"))
async def add_to_list_cmd(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Будь ласка, використовуйте формат: /add_to_list <категорія> <назва>\nПриклад: /add_to_list Фільми Початок")
        return

    parts = command.args.split(" ", 1)
    if len(parts) < 2:
        await message.answer("Будь ласка, вкажіть категорію та назву.")
        return

    category_input = parts[0].strip()
    title = parts[1].strip()

    # Find matching category
    category = next((c for c in CATEGORIES if category_input in c), None)
    if not category:
        await message.answer(f"Категорія '{category_input}' не знайдена. Оберіть одну з: {', '.join(CATEGORIES)}")
        return

    async with AsyncSessionLocal() as session:
        new_item = ListItem(user_id=message.from_user.id, category=category, title=title)
        session.add(new_item)
        await session.commit()
        await session.refresh(new_item)
    
    await message.answer(f"✅ '{title}' додано до категорії {category} (ID: {new_item.item_id})!")

@router.message(Command("update_status"))
async def update_status_cmd(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Використовуйте: /update_status <ID> <новий_статус>")
        return

    parts = command.args.split(" ", 1)
    try:
        item_id = int(parts[0])
        new_status = parts[1].strip()
    except (ValueError, IndexError):
        await message.answer("Невірний формат ID або статус.")
        return

    # Map status shortcuts
    status_map = {
        'to_watch': 'до_перегляду',
        'watching': 'переглядаю',
        'watched': 'переглянув'
    }
    status = status_map.get(new_status, new_status)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(ListItem).where(
                ListItem.item_id == item_id,
                ListItem.user_id == message.from_user.id
            ).values(status=status)
        )
        await session.commit()
        
        if result.rowcount > 0:
            await message.answer(f"✅ Статус елемента {item_id} оновлено на '{status}'.")
        else:
            await message.answer(f"❌ Елемент {item_id} не знайдений.")
