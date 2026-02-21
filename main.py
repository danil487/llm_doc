# main.py
from controllers import AppController, BotController, SyncController
from hybrid_search.utils import logger, Config
import signal
import sys
import os


class Application:
    """✅ Главный контроллер приложения"""

    def __init__(self):
        self.app_controller = AppController()
        self.bot_controller = None
        self.sync_controller = None
        self._setup_signals()

    def _setup_signals(self):
        """Настройка обработчиков сигналов"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        """Обработчик сигналов завершения"""
        logger.info("\n🛑 Получен сигнал завершения...")
        self.shutdown()
        sys.exit(0)

    def run(self):
        """✅ Единая точка входа"""
        try:
            # 1. Инициализация
            os.environ['TOKENIZERS_PARALLELISM'] = 'true'
            self.app_controller.initialize()

            # 2. Загрузка данных
            self.app_controller.load_data()

            # 3. Запуск синхронизатора
            if Config.ENABLE_PERIODIC_SYNC:
                self.sync_controller = SyncController()
                self.sync_controller.start()

            # 4. Запуск Telegram бота
            if Config.TELEGRAM_ENABLED:
                self.bot_controller = BotController()
                self.bot_controller.start()

            # 5. Основной цикл (CLI)
            self.app_controller.run_cli()

        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            self.shutdown()
            raise

    def shutdown(self):
        """✅ Корректное завершение"""
        logger.info("\n🧹 Завершение работы...")
        if self.bot_controller:
            self.bot_controller.stop()
        if self.sync_controller:
            self.sync_controller.stop()
        self.app_controller.cleanup()
        logger.info("✅ Завершено")


if __name__ == "__main__":
    app = Application()
    app.run()