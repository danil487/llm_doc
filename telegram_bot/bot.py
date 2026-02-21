# telegram_bot/bot.py
import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from hybrid_search.utils import logger, Config


class TelegramBot:
    """✅ Telegram Bot """

    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.webhook_url = Config.TELEGRAM_WEBHOOK_URL
        self.webhook_port = Config.TELEGRAM_WEBHOOK_PORT
        self.semantic = None
        self.response = None
        self.app = None
        logger.info("✅ TelegramBot инициализирован")

    def _init_rag_components(self):
        """✅ Инициализирует RAG-компоненты (ленивая)"""
        if self.semantic is None:
            from hybrid_search.search import SemanticSearch
            from rag_llm.response import Response
            self.semantic = SemanticSearch()
            self.response = Response()
            logger.info("✅ RAG-компоненты инициализированы для Telegram Bot")

    def _get_session_id(self, chat_id: int, user_id: int) -> str:
        """Генерирует уникальный session_id для Telegram-чата"""
        return f"tg_{chat_id}_{user_id}"

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /start"""
        await update.message.reply_text(
            "👋 *Привет! Я — AI-ассистент по документации Confluence.*\n\n"
            "Задавайте вопросы, и я найду ответ в базе знаний.\n\n"
            "*Команды:*\n"
            "/clear — очистить историю диалога\n"
            "/help — показать справку\n"
            "/status — статус системы"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /help"""
        await update.message.reply_text(
            "📖 *Справка*\n\n"
            "• Просто напишите вопрос — я поищу ответ в документации\n"
            "• /clear — очистить историю переписки\n"
            "• /status — проверить статус системы\n"
            "• /start — начать заново\n\n"
            "_Ответы формируются на основе данных из Confluence._"
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
                f"• Модель: `{Config.OLLAMA_MODEL}`"
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
            await update.message.reply_text("🧹 *История диалога очищена.*")
        except Exception as e:
            logger.error(f"❌ Ошибка clear_command: {e}")
            await update.message.reply_text("⚠️ Ошибка при очистке истории")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        try:
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            query = update.message.text.strip()
            session_id = self._get_session_id(chat_id, user_id)

            if not query:
                return

            # ✅ Инициализация RAG-компонентов в первом запросе
            self._init_rag_components()

            # Индикатор "печатает..."
            await update.message.chat.send_action(action="typing")
            logger.info(f"🔍 Telegram запрос от {chat_id}: {query[:100]}")

            # ✅ Асинхронный вызов блокирующих операций
            loop = asyncio.get_event_loop()
            matches = await loop.run_in_executor(None, self.semantic.search, query)

            if not matches.get('matches'):
                await update.message.reply_text(
                    "⚠️ *Ничего не найдено*\n\n"
                    "Я не нашёл релевантной информации в документации.\n"
                    "Попробуйте:\n"
                    "• Переформулировать вопрос\n"
                    "• Использовать другие ключевые слова"
                )
                return

            answer = await loop.run_in_executor(
                None,
                self.response.query_model,
                session_id,
                query,
                matches
            )

            # Telegram лимит 4096 символов
            if len(answer) > 4000:
                chunks = [answer[i:i + 4000] for i in range(0, len(answer), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='Markdown')
            else:
                await update.message.reply_text(answer, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения: {e}")
            await update.message.reply_text(
                "⚠️ *Ошибка*\n\nПроизошла ошибка при обработке запроса. Попробуйте позже."
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Логирование ошибок"""
        logger.error(f"❌ Telegram error: {context.error}")

    def run_polling(self):
        """Запуск бота в режиме polling (рекомендуется)"""
        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("clear", self.clear_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_error_handler(self.error_handler)
        logger.info("🚀 Telegram Bot запущен (polling mode)")
        self.app.run_polling(drop_pending_updates=True)

    def run_webhook(self):
        """Запуск бота в режиме webhook (требует HTTPS)"""
        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("clear", self.clear_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_error_handler(self.error_handler)
        logger.info(f"🚀 Telegram Bot запущен (webhook mode: {self.webhook_url})")
        self.app.run_webhook(
            listen="0.0.0.0",
            port=self.webhook_port,
            url_path=self.token,
            webhook_url=self.webhook_url
        )

    def run(self):
        """Автовыбор режима запуска"""
        if self.webhook_url:
            self.run_webhook()
        else:
            self.run_polling()
