# controllers/sync_controller.py
import threading
import time

from hybrid_search.update import UpdateDatabase
from hybrid_search.utils import logger


class SyncController:
    """✅ Контроллер фоновой синхронизации"""

    def __init__(self):
        self._updater = None
        self._running = False
        self._thread = None

    def start(self):
        """Запуск синхронизатора"""
        self._running = True
        self._thread = threading.Thread(target=self._run_sync, daemon=True)
        self._thread.start()
        logger.info("✅ Синхронизатор запущен (Thread)")

    def _run_sync(self):
        """Фоновая синхронизация"""
        self._updater = UpdateDatabase()
        while self._running:
            try:
                stats = self._updater.sync_changed_pages(max_pages=50)
                if stats['updated'] > 0:
                    logger.info(f"✅ Обновлено: {stats['updated']}/{stats['checked']}")
                else:
                    logger.info(f"✅ Изменений нет ({stats['checked']} проверено)")
                time.sleep(300)  # 5 минут
            except Exception as e:
                logger.error(f"❌ Ошибка синхронизации: {e}")
                time.sleep(60)

    def stop(self):
        """Остановка синхронизатора"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("🛑 Синхронизатор остановлен")
