# main.py

from hybrid_search.search import SemanticSearch
from hybrid_search.update import UpdateDatabase
from hybrid_search.database import Database
from rag_llm.response import Response
from multiprocessing import Process
import os
import sys
import uuid
import time
import signal
from hybrid_search.utils import logger

# Глобальные инстансы
semantic = SemanticSearch()
response = Response()


def is_first_run() -> bool:
    """Проверяет, был ли уже выполнен первоначальный индекс"""
    try:
        db = Database()
        doc_count = db.count()

        if doc_count == 0:
            logger.info(f"📭 База пуста (0 документов) — требуется полная загрузка")
            return True
        else:
            logger.info(f"📚 В базе {doc_count} документов — пропускаем полную загрузку")
            return False
    except Exception as e:
        logger.error(f"⚠️  Не удалось проверить базу: {e}")
        return True


def run_update():
    """Фоновая задача периодического обновления"""
    db = UpdateDatabase()
    try:
        time.sleep(10)  # Даём основному процессу время на инициализацию
        db.periodic_update(check_interval=300, max_pages_per_cycle=50)
    except Exception as e:
        logger.error(f"❌ Ошибка в фоновом обновлении: {e}")


def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info("\n🛑 Получен сигнал завершения...")
    sys.exit(0)


# ===== TELEGRAM BOT =====
def run_telegram_bot():
    """Точка входа для запуска Telegram-бота в отдельном процессе"""
    if os.getenv("TELEGRAM_ENABLED", "false").lower() != "true":
        return

    try:
        from telegram_bot.bot import TelegramBot
        bot = TelegramBot()
        bot.run()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска Telegram Bot: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    session_id = f"session_{uuid.uuid4().hex[:8]}"
    logger.info(f"🆔 Session ID: {session_id}")

    os.environ['TOKENIZERS_PARALLELISM'] = 'true'

    force_reload = os.getenv('FORCE_RELOAD', 'false').lower() == 'true'
    skip_load = os.getenv('SKIP_LOAD', 'false').lower() == 'true'
    enable_sync = os.getenv('ENABLE_PERIODIC_SYNC', 'true').lower() == 'true'

    db_updater = None
    proc = None
    tg_proc = None

    try:
        # Проверка необходимости загрузки
        first_run = is_first_run()

        if force_reload:
            logger.warning("⚠️  FORCE_RELOAD=true — выполняем полную перезагрузку")
            first_run = True
        elif skip_load:
            logger.info("⏭️  SKIP_LOAD=true — пропускаем загрузку")
            first_run = False

        # Полная загрузка (только первый раз)
        if first_run:
            logger.info("=" * 60)
            logger.info("🔄 ПЕРВИЧНАЯ ИНДЕКСАЦИЯ (40-60 минут)")
            logger.info("=" * 60)

            db_updater = UpdateDatabase()
            db_updater.load_all()

            logger.info("✅ Первичная индексация завершена!")
            logger.info("💡 В следующий раз загрузка будет пропущена")
        else:
            logger.info("✅ База уже проиндексирована")

        # Фоновый синхронизатор
        if enable_sync:
            logger.info("🔄 Запуск фонового синхронизатора (5 мин)...")
            proc = Process(target=run_update)
            proc.start()
            logger.info(f"✅ Фоновый процесс запущен (PID: {proc.pid})")

        # Проверка Ollama
        from rag_llm.model import Model

        llm = Model()
        if not llm.check_model_available():
            logger.warning(f"⚠️  Модель {llm.model_name} не найдена в Ollama!")

        logger.info("=" * 60)
        logger.info("🎯 RAG-система готова к работе!")
        logger.info("=" * 60)
        logger.info("Команды: /clear, /exit, /help, /sync")
        logger.info("=" * 60)

        # ===== Запуск Telegram-бота =====
        if os.getenv("TELEGRAM_ENABLED", "false").lower() == "true":
            logger.info("🤖 Запуск Telegram Bot...")
            tg_proc = Process(target=run_telegram_bot, daemon=True)
            tg_proc.start()
            logger.info(f"✅ Telegram Bot запущен (PID: {tg_proc.pid})")

        while True:
            try:
                query = input("\n❓ Ваш вопрос: ").strip()

                if not query:
                    continue

                if query.lower() in ['/exit', '/quit', '/q']:
                    logger.info("👋 Выход...")
                    break
                elif query.lower() == '/clear':
                    response.terminate(session_id)
                    logger.info("🧹 История очищена")
                    continue
                elif query.lower() == '/help':
                    logger.info("📖 Команды: /clear, /exit, /help, /sync")
                    continue
                elif query.lower() == '/sync':
                    logger.info("🔄 Принудительная синхронизация...")
                    if db_updater is None:
                        db_updater = UpdateDatabase()
                    stats = db_updater.sync_changed_pages(max_pages=20)
                    logger.info(f"✅ Синхронизировано: {stats['updated']} страниц")
                    continue

                logger.info("🔍 Поиск...")
                matches = semantic.search(query)

                if not matches.get('matches'):
                    logger.info("⚠️  Ничего не найдено")
                    continue

                logger.info("\n🤖 Ответ:")
                logger.info("-" * 60)
                answer = response.query_model(session_id, query, matches)
                logger.info(answer)
                logger.info("-" * 60)

                if matches.get('matches'):
                    logger.info("\n📎 Источники:")
                    for i, match in enumerate(matches['matches'][:3], 1):
                        doc_id = match.get('id', 'N/A')
                        score = match.get('score', 0)
                        logger.info(f"   {i}. {doc_id} (score: {score:.4f})")

            except KeyboardInterrupt:
                logger.info("\n⏸️  Прервано")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")
                continue

    except KeyboardInterrupt:
        logger.info("\n🛑 Остановка...")

    finally:
        logger.info("\n🧹 Завершение...")
        if proc and proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
        if tg_proc and tg_proc.is_alive():
            tg_proc.terminate()
            tg_proc.join(timeout=5)
        response.terminate(session_id)
        logger.info("✅ Завершено")
