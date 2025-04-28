from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from app.database import init_db, create_project, get_projects
from app.schemas import BotProject
from fastapi.responses import FileResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from zipfile import ZipFile
from typing import List
import shutil
import os
import json

# Новый импорт для CORS
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Конфигурация CORS (добавлено!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Фронтенд на React обычно работает здесь
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

@app.get("/")
def root():
    return {"message": "Сервер конструктора Telegram-ботов запущен"}

@app.post("/projects")
async def create_new_project(
    project: str = Form(...)
):
    """
    Создание нового проекта: принимает JSON как строку через form-data
    """
    try:
        project_dict = json.loads(project)
        bot_project = BotProject(**project_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга проекта: {e}")

    project_id = create_project(bot_project)
    return {"status": "created", "project_id": project_id}

@app.post("/projects/{project_id}/media")
async def upload_media(
    project_id: int,
    files: List[UploadFile] = File(...)
):
    """
    Загрузка медиафайлов для проекта
    """
    project = get_projects(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    media_dir = Path(__file__).parent.parent / "media" / str(project_id)
    media_dir.mkdir(parents=True, exist_ok=True)

    for upload in files:
        dest = media_dir / upload.filename
        with open(dest, "wb") as f:
            f.write(await upload.read())

    return {"status": "media_uploaded", "count": len(files)}

@app.get("/projects/{project_id}/export")
def export_bot(project_id: int):
    """
    Экспорт проекта в zip-архив
    """
    project = get_projects(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    template_type = project["template_type"]
    template_path = Path(__file__).parent / "templates" / template_type
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    export_dir = Path(__file__).parent / "exports" / f"project_{project_id}"
    export_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(template_path))
    for tpl_file in template_path.glob("*.j2"):
        template = env.get_template(tpl_file.name)
        rendered = template.render(project=project)
        output_file = export_dir / tpl_file.name.replace(".j2", "")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(rendered)

    with open(export_dir / ".env", "w", encoding="utf-8") as f:
        f.write(f'TOKEN={project["token"]}\n')

    with open(export_dir / "requirements.txt", "w", encoding="utf-8") as f:
        f.write("aiogram\n")
        f.write("python-dotenv\n")
        f.write("openpyxl\n")

    with open(export_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(f"# {project['name']}\n\n")
        f.write(f"{project['description']}\n\n")
        f.write("## Как запустить бота:\n")
        f.write("```bash\n")
        f.write("pip install -r requirements.txt\n")
        f.write("python bot.py\n")
        f.write("```\n")

    with open(export_dir / "run.py", "w", encoding="utf-8") as f:
        f.write("import os\n")
        f.write("import subprocess\n")
        f.write("import sys\n\n")
        f.write("def install_requirements():\n")
        f.write("    try:\n")
        f.write("        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r requirements.txt'])\n")
        f.write("    except subprocess.CalledProcessError as e:\n")
        f.write("        print('Ошибка при установке зависимостей:', e)\n")
        f.write("        sys.exit(1)\n\n")
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

    # Копируем медиа-файлы, если есть
    media_src = Path(__file__).parent.parent / "media" / str(project_id)
    media_dst = export_dir / "media"
    if media_src.exists():
        shutil.copytree(media_src, media_dst)

    # Создаём ZIP архив
    zip_path = Path(__file__).parent / "exports" / f"project_{project_id}.zip"
    with ZipFile(zip_path, "w") as zipf:
        for file in export_dir.rglob("*"):
            zipf.write(file, arcname=file.relative_to(export_dir))

    shutil.rmtree(export_dir)

    return FileResponse(zip_path, filename=f"{project['name']}.zip", media_type="application/zip")
