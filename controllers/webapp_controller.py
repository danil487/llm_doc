# controllers/webapp_controller.py
import threading
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os

from hybrid_search.utils import logger, Config
from hybrid_search.dynamic_config import dynamic_config

app = FastAPI(title="RAG Settings API")

# Настройка CORS (в разработке можно разрешить все источники)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем статические файлы Angular (после сборки)
angular_dist = os.path.join(os.path.dirname(__file__), "..", "webapp", "dist", "rag-settings")
if os.path.exists(angular_dist):
    app.mount("/", StaticFiles(directory=angular_dist, html=True), name="static")
else:
    logger.warning("Angular dist not found, static files not mounted")


# Модели запросов/ответов
class AuthRequest(BaseModel):
    token: str


class AuthResponse(BaseModel):
    success: bool


class ConfigUpdate(BaseModel):
    updates: Dict[str, Any]


def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    admin_token = Config.ADMIN_TOKEN
    if token != admin_token:
        raise HTTPException(status_code=403, detail="Invalid token")
    return token


@app.post("/api/auth", response_model=AuthResponse)
async def auth(request: AuthRequest):
    if request.token == Config.ADMIN_TOKEN:
        return AuthResponse(success=True)
    raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/api/config/schema")
async def get_schema(token: str = Depends(verify_token)):
    """Возвращает метаданные о настройках для динамического построения формы."""
    defaults = dynamic_config._get_defaults_from_static()
    current = dynamic_config.get_all()
    schema = []
    for key, default in defaults.items():
        schema.append({
            "key": key,
            "type": type(default).__name__,
            "default": default,
            "current": current.get(key, default),
            # Можно добавить описание из отдельного словаря
        })
    return schema


@app.get("/api/config")
async def get_config(token: str = Depends(verify_token)):
    return dynamic_config.get_all()


@app.post("/api/config")
async def update_config(update: ConfigUpdate, token: str = Depends(verify_token)):
    try:
        new_config = dynamic_config.set(update.updates)
        return new_config
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class WebAppController:
    """Контроллер для запуска FastAPI сервера в отдельном потоке."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._server = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        logger.info("✅ WebApp API запущен (Thread)")

    def _run_server(self):
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
        self._server = uvicorn.Server(config)
        self._server.run()

    def stop(self):
        self._running = False
        if self._server:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("🛑 WebApp API остановлен")
