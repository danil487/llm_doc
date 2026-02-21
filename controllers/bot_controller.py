# controllers/bot_controller.py
from hybrid_search.utils import logger, Config
import threading


class BotController:
    """✅ Контроллер Telegram бота """

    def __init__(self):
        self._bot = None
        self._running = False
        self._thread = None

    def start(self):
        """Запуск бота в отдельном потоке"""
        self._running = True
        self._thread = threading.Thread(target=self._run_bot, daemon=True)
        self._thread.start()
        logger.info("✅ Telegram Bot запущен")

    def _run_bot(self):
        """Точка входа бота (внутри потока)"""
        try:
            # ✅ Импорты внутри потока (избегаем singleton-проблем)
            from telegram_bot.bot import TelegramBot

            bot = TelegramBot()
            bot.run()
        except Exception as e:
            logger.error(f"❌ Ошибка бота: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def stop(self):
        """Остановка бота"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("🛑 Telegram Bot остановлен")
