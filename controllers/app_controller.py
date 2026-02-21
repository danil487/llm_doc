# controllers/app_controller.py
import uuid

from hybrid_search.database import Database
from hybrid_search.search import SemanticSearch
from hybrid_search.update import UpdateDatabase
from hybrid_search.utils import logger, Config
from rag_llm.response import Response


class AppController:
    """✅ Контроллер основного приложения"""

    def __init__(self):
        self.session_id = f"session_{uuid.uuid4().hex[:8]}"
        self._semantic = None
        self._response = None
        self._db_updater = None

    def initialize(self):
        """Ленивая инициализация компонентов"""
        Config.log()
        logger.info(f"🆔 Session ID: {self.session_id}")

    def _get_semantic(self):
        """✅ Ленивая инициализация SemanticSearch"""
        if self._semantic is None:
            self._semantic = SemanticSearch()
        return self._semantic

    def _get_response(self):
        """✅ Ленивая инициализация Response"""
        if self._response is None:
            self._response = Response()
        return self._response

    def load_data(self):
        """Управление загрузкой данных"""
        first_run = self._check_first_run()

        if Config.FORCE_RELOAD:
            logger.warning("⚠️  FORCE_RELOAD=true — выполняем полную перезагрузку")
            first_run = True
        elif Config.SKIP_LOAD:
            logger.info("⏭️  SKIP_LOAD=true — пропускаем загрузку")
            return

        if first_run:
            logger.info("=" * 60)
            logger.info("🔄 ПЕРВИЧНАЯ ИНДЕКСАЦИЯ (40-60 минут)")
            logger.info("=" * 60)
            self._db_updater = UpdateDatabase()
            self._db_updater.load_all()
            logger.info("✅ Первичная индексация завершена!")
        else:
            logger.info("✅ База уже проиндексирована")

        # Проверка Ollama
        from rag_llm.model import Model
        llm = Model()
        if not llm.check_model_available():
            logger.warning(f"⚠️  Модель {llm.model_name} не найдена в Ollama!")

    def _check_first_run(self) -> bool:
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

    def run_cli(self):
        """CLI цикл"""
        logger.info("=" * 60)
        logger.info("🎯 RAG-система готова к работе!")
        logger.info("=" * 60)
        logger.info("Команды: /clear, /exit, /help, /sync")
        logger.info("=" * 60)

        while True:
            try:
                query = input("\n❓ Ваш вопрос: ").strip()
                if not query:
                    continue

                if self._handle_command(query):
                    continue

                self._process_query(query)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")

    def _handle_command(self, query: str) -> bool:
        """Обработка команд"""
        cmd = query.lower()
        if cmd in ['/exit', '/quit', '/q']:
            logger.info("👋 Выход...")
            return True
        elif cmd == '/clear':
            self._get_response().terminate(self.session_id)
            logger.info("🧹 История очищена")
            return True
        elif cmd == '/sync':
            self._sync_now()
            return True
        elif cmd == '/help':
            logger.info("📖 Команды: /clear, /exit, /help, /sync")
            return True
        return False

    def _process_query(self, query: str):
        """Обработка запроса"""
        logger.info("🔍 Поиск...")
        matches = self._get_semantic().search(query)

        if not matches.get('matches'):
            logger.info("⚠️  Ничего не найдено")
            return

        logger.info("\n🤖 Ответ:")
        logger.info("-" * 60)
        answer = self._get_response().query_model(self.session_id, query, matches)
        logger.info(answer)
        logger.info("-" * 60)

        if matches.get('matches'):
            logger.info("\n📎 Источники:")
            for i, match in enumerate(matches['matches'][:3], 1):
                doc_id = match.get('id', 'N/A')
                score = match.get('score', 0)
                logger.info(f"   {i}. {doc_id} (score: {score:.4f})")

    def _sync_now(self):
        """Принудительная синхронизация"""
        logger.info("🔄 Принудительная синхронизация...")
        if self._db_updater is None:
            self._db_updater = UpdateDatabase()
        stats = self._db_updater.sync_changed_pages(max_pages=20)
        logger.info(f"✅ Синхронизировано: {stats['updated']} страниц")

    def cleanup(self):
        """Очистка ресурсов"""
        if self._response:
            self._response.terminate(self.session_id)
        logger.info("🧹 Ресурсы очищены")
