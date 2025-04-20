from aiogram import Bot, Dispatcher, executor, types

bot = Bot(token="")
dp = Dispatcher(bot)

questions = [{'question': 'Какой язык программирования используется в этом проекте?', 'options': ['Python', 'JavaScript', 'C++'], 'correct': 'Python'}, {'question': 'Какой фреймворк используется для сервера?', 'options': ['Flask', 'FastAPI', 'Django'], 'correct': 'FastAPI'}]

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    for q in questions:
        options = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(q["options"]))
        await message.answer(f'{q["question"]}\n{options}')

if __name__ == '__main__':
    executor.start_polling(dp)