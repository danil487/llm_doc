# controllers/bot_controller.py
from hybrid_search.utils import logger, Config
import threading
import asyncio


class BotController:
    """✅ Контроллер Telegram бота (с правильной инициализацией)"""

    def __init__(self):
        self._running = False
        self._thread = None
        self._loop = None

    def start(self):
        """Запуск бота в отдельном потоке"""
        self._running = True
        self._thread = threading.Thread(target=self._run_bot, daemon=True)
        self._thread.start()
        logger.info("✅ Telegram Bot запущен (Thread)")

    def _run_bot(self):
        """Точка входа бота (внутри потока)"""
        try:
            # ✅ Создаём новый event loop для потока
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            # ✅ Импорты внутри потока
            from telegram.ext import Application, CommandHandler, MessageHandler, filters
            from telegram_bot.bot import TelegramBot

            bot = TelegramBot()

            # ✅ Создаём приложение
            app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

            # Регистрируем обработчики
            app.add_handler(CommandHandler("start", bot.start))
            app.add_handler(CommandHandler("help", bot.help_command))
            app.add_handler(CommandHandler("status", bot.status_command))
            app.add_handler(CommandHandler("clear", bot.clear_command))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
            app.add_error_handler(bot.error_handler)

            # ✅ Запускаем polling в event loop
            logger.info("🚀 Telegram Bot запущен (polling mode)")
            self._loop.run_until_complete(self._start_app(app))

        except Exception as e:
            logger.error(f"❌ Ошибка бота: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            if self._loop:
                self._loop.close()

    async def _start_app(self, app):
        """✅ Правильная инициализация и запуск приложения"""
        try:
            # ✅ Инициализируем приложение
            await app.initialize()

            # ✅ Запускаем updater
            await app.updater.start_polling(drop_pending_updates=True)

            # ✅ Запускаем приложение
            await app.start()

            # ✅ Держим поток живым
            while self._running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"❌ Ошибка в _start_app: {e}")
            raise
        finally:
            # ✅ Корректная остановка
            await app.stop()
            await app.updater.stop()
            await app.shutdown()

    def stop(self):
        """Остановка бота"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("🛑 Telegram Bot остановлен")
