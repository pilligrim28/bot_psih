import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from questions import QUESTIONS, calculate_result

# Быстрое хранилище в памяти (FSM)
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

logging.basicConfig(level=logging.INFO)

# --- FSM состояния ---
class TestState(StatesGroup):
    answering = State()  # режим ответа на вопросы

# Хранилище ответов пользователя (временно в памяти)
user_answers = {}

# --- Приветствие ---
@dp.message(Command("start"))
async def start_command(message: Message):
    # Фото должно лежать в папке images, например "welcome.jpg"
    photo = FSInputFile("images/welcome.jpg")
    text = (
        "Привет, я Светлана Кустовская.\n"
        "Женский коуч и телесный терапевт.\n\n"
        "Этот тест для тебя, если ты узнаёшь хотя бы одну из этих болей:\n\n"
        "— не понимаешь, чего хочешь и куда идёшь;\n"
        "— сложно строить отношения (или их нет);\n"
        "— постоянно сомневаешься в себе, низкая самооценка;\n"
        "— устала быть удобной, не живёшь своей жизнью;\n"
        "— с деньгами не выходит: стыдно брать, не растёшь.\n\n"
        "За 2 минуты ты получишь конкретный план из 4 шагов, благодаря которым:\n\n"
        "— перестанешь заслуживать любовь и начнёшь выбирать себя;\n"
        "— создашь мотивацию и энергичное состояние;\n"
        "— научишься выстраивать границы и говорить «нет»;\n"
        "— выйдешь из абьюзивных сценариев в отношениях;\n"
        "— обретёшь уверенность.\n\n"
        "В конце — твой личный план из 4 шагов, с чего начать.\n\n"
        "👇 Отвечай честно. Это просто тест, который покажет, где ты сейчас."
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Начать тест", callback_data="start_test")]]
    )
    await message.answer_photo(photo=photo, caption=text, reply_markup=keyboard)

# --- Начало теста ---
@dp.callback_query(F.data == "start_test")
async def start_test(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()  # убираем приветствие (опционально)
    user_answers[callback.from_user.id] = []
    await state.set_state(TestState.answering)
    await state.update_data(question_index=0)
    await send_question(callback.message, 0, callback.from_user.id)
    await callback.answer()

async def send_question(message: Message, index: int, user_id: int):
    if index >= len(QUESTIONS):
        # Тест окончен
        answers_list = user_answers.get(user_id, [])
        result_text = calculate_result(answers_list)
        final_msg = (
            f"✨ Твой результат ✨\n\n{result_text}\n\n"
            "Если хочешь глубже разобрать свой запрос — напиши мне @svetlana_kustovskaya (ссылка для примера)"
        )
        await message.answer(final_msg)
        # Чистим данные пользователя
        if user_id in user_answers:
            del user_answers[user_id]
        return
    
    q = QUESTIONS[index]
    text = q["text"]
    # Все варианты в одну строку
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=key, callback_data=f"ans_{key}")
        for key in q["options"].keys()
    ]])

    # Отправляем вопрос + фото (q1.jpg, q2.jpg и т.д. для каждого вопроса)
    photo = FSInputFile(f"images/q{index + 1}.jpg")
    await message.answer_photo(photo=photo, caption=text, reply_markup=kb)

@dp.callback_query(TestState.answering, F.data.startswith("ans_"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    answer_letter = callback.data.split("_")[1]  # "А", "Б" и т.д.

    # Сохраняем ответ
    if user_id not in user_answers:
        user_answers[user_id] = []
    user_answers[user_id].append(answer_letter)

    # Получаем текущий индекс вопроса
    data = await state.get_data()
    current_index = data.get("question_index", 0)
    next_index = current_index + 1

    # Формируем клавиатуру с галочкой на выбранном и деактивируем все кнопки
    q = QUESTIONS[current_index] if current_index < len(QUESTIONS) else QUESTIONS[-1]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"{'✅ ' if key == answer_letter else ''}{key}",
            callback_data=f"done_{key}"  # другой префикс — не сработает фильтр ans_
        )
        for key in q["options"].keys()
    ]])
    await callback.message.edit_reply_markup(reply_markup=kb)

    if next_index < len(QUESTIONS):
        await state.update_data(question_index=next_index)
        # Отправляем следующий вопрос новым сообщением
        await send_question(callback.message, next_index, user_id)
    elif next_index == len(QUESTIONS):
        # Последний вопрос — обрабатываем ответ и показываем результат
        await state.update_data(question_index=next_index)
        await callback.message.delete()
        await send_question(callback.message, next_index, user_id)
    else:
        # Тест уже закончен, ничего не делаем
        pass

    await callback.answer()

@dp.callback_query(TestState.answering, F.data.startswith("done_"))
async def handle_already_answered(callback: CallbackQuery):
    await callback.answer("Вы уже ответили на этот вопрос", show_alert=True)

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())