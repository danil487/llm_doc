# telegram_bot/bot.py
import asyncio

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from hybrid_search.utils import logger, Config


class TelegramBot:
    """Telegram Bot с поддержкой длительного 'печатает...' """

    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.webhook_url = Config.TELEGRAM_WEBHOOK_URL
        self.webhook_port = Config.TELEGRAM_WEBHOOK_PORT
        self.semantic = None
        self.response = None
        self.app = None
        logger.info("✅ TelegramBot инициализирован")

    def _init_rag_components(self):
        """Инициализирует RAG-компоненты (ленивая)"""
        if self.semantic is None:
            from hybrid_search.search import SemanticSearch
            from rag_llm.response import Response
            self.semantic = SemanticSearch()
            self.response = Response()
            logger.info("✅ RAG-компоненты инициализированы для Telegram Bot")

    def _get_session_id(self, chat_id: int, user_id: int) -> str:
        """Генерирует уникальный session_id для Telegram-чата"""
        return f"tg_{chat_id}_{user_id}"

    async def _keep_typing(self, update: Update, stop_event: asyncio.Event):
        """Фоновая задача: отправляет 'typing' каждые 5 секунд до сигнала остановки"""
        try:
            while not stop_event.is_set():
                await update.message.chat.send_action(action="typing")
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            # задача отменена, выходим
            pass
        except Exception as e:
            logger.error(f"Ошибка в _keep_typing: {e}")

    async def _start_typing_task(self, update: Update):
        """Запускает фоновую задачу отправки 'печатает...' и возвращает (stop_event, task)"""
        stop_event = asyncio.Event()
        task = asyncio.create_task(self._keep_typing(update, stop_event))
        return stop_event, task

    async def _stop_typing_task(self, stop_event: asyncio.Event, task: asyncio.Task):
        """Останавливает фоновую задачу отправки 'печатает...'"""
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /start"""
        await update.message.reply_text(
            "👋 *Привет! Я — AI-ассистент по документации Confluence.*\n\n"
            "Задавайте вопросы, и я найду ответ в базе знаний.\n\n"
            "*Команды:*\n"
            "/clear — очистить историю диалога\n"
            "/help — показать справку\n"
            "/status — статус системы",
            parse_mode=ParseMode.MARKDOWN
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /help"""
        await update.message.reply_text(
            "📖 *Справка*\n\n"
            "• Просто напишите вопрос — я поищу ответ в документации\n"
            "• /clear — очистить историю переписки\n"
            "• /status — проверить статус системы\n"
            "• /start — начать заново\n\n"
            "_Ответы формируются на основе данных из Confluence._",
            parse_mode=ParseMode.MARKDOWN
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /status"""
        try:
            from hybrid_search.database import Database
            db = Database()
            count = db.count()
            await update.message.reply_text(
                f"📊 *Статус системы:*\n\n"
                f"• Документов в базе: `{count}`\n"
                f"• Статус: ✅ Работает\n"
                f"• Модель: `{Config.OLLAMA_MODEL}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"❌ Ошибка status_command: {e}")
            await update.message.reply_text(f"⚠️ Ошибка получения статуса: {e}")

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /clear"""
        try:
            self._init_rag_components()
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            session_id = self._get_session_id(chat_id, user_id)
            self.response.terminate(session_id)
            await update.message.reply_text("🧹 *История диалога очищена.*", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"❌ Ошибка clear_command: {e}")
            await update.message.reply_text("⚠️ Ошибка при очистке истории")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений с поддержкой длительного 'печатает...'"""
        try:
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            query = update.message.text.strip()
            session_id = self._get_session_id(chat_id, user_id)

            if not query:
                return

            # Сразу запускаем фоновую задачу "печатает..." – она будет активна всё время обработки
            stop_typing, typing_task = await self._start_typing_task(update)

            try:
                # Инициализация RAG-компонентов (если ещё не сделано)
                self._init_rag_components()

                logger.info(f"🔍 Telegram запрос от {chat_id}: {query[:100]}")

                # Асинхронный вызов поиска
                loop = asyncio.get_event_loop()
                matches = await loop.run_in_executor(None, self.semantic.search, query)

                if not matches.get('matches'):
                    await update.message.reply_text(
                        "⚠️ *Ничего не найдено*\n\n"
                        "Я не нашёл релевантной информации в документации.\n"
                        "Попробуйте:\n"
                        "• Переформулировать вопрос\n"
                        "• Использовать другие ключевые слова",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return

                # Генерация ответа
                answer = await loop.run_in_executor(
                    None,
                    self.response.query_model,
                    session_id,
                    query,
                    matches
                )

                # Отправка ответа (с учётом лимита)
                if len(answer) > 4000:
                    chunks = [answer[i:i + 4000] for i in range(0, len(answer), 4000)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
                else:
                    await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN)

            finally:
                await self._stop_typing_task(stop_typing, typing_task)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения: {e}")
            # Если задача typing ещё существует, останавливаем
            if 'typing_task' in locals() and not typing_task.done():
                await self._stop_typing_task(stop_typing, typing_task)
            await update.message.reply_text(
                "⚠️ *Ошибка*\n\nПроизошла ошибка при обработке запроса. Попробуйте позже.",
                parse_mode=ParseMode.MARKDOWN
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Логирование ошибок"""
        logger.error(f"❌ Telegram error: {context.error}")

