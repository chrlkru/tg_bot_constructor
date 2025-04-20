from fastapi import FastAPI, HTTPException
from app.database import init_db, create_project, get_projects
from app.schemas import BotProject

app = FastAPI()
init_db()

@app.get("/")
def root():
    return {"message": "Сервер конструктора Telegram-ботов запущен"}

@app.post("/projects")
def create_new_project(project: BotProject):
    project_id = create_project(project)
    return {"status": "created", "project_id": project_id}

@app.get("/projects")
def list_projects():
    return get_projects()

@app.get("/projects/{project_id}")
def get_single_project(project_id: int):
    project = get_projects(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project
from fastapi.responses import FileResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from zipfile import ZipFile
import shutil

@app.get("/projects/{project_id}/export")
def export_bot(project_id: int):
    project = get_projects(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    template_type = project["template_type"]
    template_path = Path(__file__).parent / "templates" / template_type
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Папка для генерации
    export_dir = Path(__file__).parent / "exports" / f"project_{project_id}"
    export_dir.mkdir(parents=True, exist_ok=True)

    # Генерация bot.py из шаблона
    env = Environment(loader=FileSystemLoader(template_path))
    for tpl_file in template_path.glob("*.j2"):
        template = env.get_template(tpl_file.name)
        rendered = template.render(project=project)
        output_file = export_dir / tpl_file.name.replace(".j2", "")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(rendered)

    # Добавим .env файл
    with open(export_dir / ".env", "w", encoding="utf-8") as f:
        f.write(f'TOKEN={project["token"]}\n')

    # Добавим requirements.txt
    with open(export_dir / "requirements.txt", "w", encoding="utf-8") as f:
        f.write("aiogram\npython-dotenv\n")

    # Добавим README.md
    with open(export_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(f"# {project['name']}\n\n")
        f.write(f"{project['description']}\n\n")
        f.write("## Как запустить бота:\n")
        f.write("```bash\n")
        f.write("pip install -r requirements.txt\n")
        f.write("python bot.py\n")
        f.write("```\n")

    # Добавим run.py (опционально)
    with open(export_dir / "run.py", "w", encoding="utf-8") as f:
        f.write("import os\n")
        f.write("import subprocess\n")
        f.write("import sys\n\n")
        f.write("# Установка зависимостей из requirements.txt\n")
        f.write("def install_requirements():\n")
        f.write("    try:\n")
        f.write("        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])\n")
        f.write("    except subprocess.CalledProcessError as e:\n")
        f.write("        print('Ошибка при установке зависимостей:', e)\n")
        f.write("        sys.exit(1)\n\n")
        f.write("# Запуск Telegram-бота\n")
        f.write("def run_bot():\n")
        f.write("    from aiogram import Bot, Dispatcher, executor, types\n")
        f.write("    from dotenv import load_dotenv\n\n")
        f.write("    load_dotenv()\n")
        f.write("    bot = Bot(token=os.getenv('TOKEN'))\n")
        f.write("    dp = Dispatcher(bot)\n\n")
        f.write("    @dp.message_handler(commands=['start'])\n")
        f.write("    async def start(message: types.Message):\n")
        f.write("        await message.answer('Бот запущен и готов к работе!')\n\n")
        f.write("    executor.start_polling(dp)\n\n")
        f.write("if __name__ == '__main__':\n")
        f.write("    install_requirements()\n")
        f.write("    run_bot()\n")

    # Упаковываем всё в ZIP
    zip_path = Path(__file__).parent / "exports" / f"project_{project_id}.zip"
    with ZipFile(zip_path, "w") as zipf:
        for file in export_dir.glob("*"):
            zipf.write(file, arcname=file.name)

    # Удаляем временную папку
    shutil.rmtree(export_dir)

    return FileResponse(zip_path, filename=f"{project['name']}.zip", media_type="application/zip")
