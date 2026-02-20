# hybrid_search/confluence.py

from hybrid_search.utils import load_env_variable, make_request, initialize_auth, singleton, logger, \
    extract_metadata_from_confluence, Config


@singleton
class ConfluenceAPI:
    def __init__(self):
        self.api_url = Config.CONFLUENCE_URL
        self.space_name = Config.CONFLUENCE_SPACE_NAME
        self.auth_token = initialize_auth()
        logger.info(f"✅ ConfluenceAPI: {self.api_url}")

    def get_space_id(self) -> str:
        """Получение ID пространства"""
        url = f"{self.api_url}/rest/api/space"
        params = {'spaceKey': self.space_name} if self.space_name else {'limit': 50}

        data = make_request(url, self.auth_token, params=params)
        results = data.get('results', [])

        if not results and 'key' in data and data.get('key') == self.space_name:
            logger.info(f"✅ Пространство: {data.get('key')} (id: {data.get('id')})")
            return data['id']

        for space in results:
            if space.get('key') == self.space_name or space.get('name') == self.space_name:
                logger.info(f"✅ Пространство: {space.get('key')} (id: {space.get('id')})")
                return space['id']

        available = [f"{s.get('key')}={s.get('name')}" for s in results[:10]]
        raise ValueError(f"❌ Пространство '{self.space_name}' не найдено. Доступные: {available}")

    def get_page_ids(self, space_id: str) -> dict:
        """Получение списка страниц с базовыми метаданными"""
        page_info = {}  # {page_id: {'title': ..., 'version': ..., 'url': ...}}
        start = 0
        limit = 100

        while True:
            url = f"{self.api_url}/rest/api/content"
            params = {
                'spaceKey': self.space_name,
                'type': 'page',
                'start': start,
                'limit': limit,
                'expand': 'version,space'
            }

            data = make_request(url, self.auth_token, params=params)
            results = data.get('results', [])

            for page in results:
                # ✅ ЗАЩИТА: проверяем, что page — это dict
                if not isinstance(page, dict):
                    logger.warning(f"⚠️  Пропущен некорректный элемент page: {type(page)} = {page}")
                    continue

                page_id = page.get('id')
                if not page_id:
                    logger.warning(f"⚠️  Пропущена страница без ID: {page}")
                    continue

                # ✅ Преобразуем ID в строку для консистентности
                page_id = str(page_id)

                # ✅ Безопасное извлечение вложенных полей
                version_info = page.get('version', {})
                if not isinstance(version_info, dict):
                    version_info = {}

                space_info = page.get('space', {})
                if not isinstance(space_info, dict):
                    space_info = {}

                page_info[page_id] = {
                    'title': page.get('title', 'Без названия'),
                    'version': version_info.get('number', 1),
                    'space_key': space_info.get('key', ''),
                    'space_name': space_info.get('name', ''),
                    'url': f"{self.api_url}/pages/viewpage.action?pageId={page_id}"
                }

            if len(results) < limit:
                break
            start += limit

        logger.info(f"✅ Найдено страниц: {len(page_info)}")
        return page_info

    def get_page_full(self, page_id: str) -> dict:
        """
        Получение полной информации о странице (контент + метаданные).

        Returns:
            Dict с полями: content (HTML), metadata (расширенные метаданные)
        """
        url = f"{self.api_url}/rest/api/content/{page_id}"
        params = {'expand': 'body.view,version,space,labels'}

        data = make_request(url, self.auth_token, params=params)

        return {
            'content': data.get('body', {}).get('view', {}).get('value', ''),
            'metadata': extract_metadata_from_confluence(data, page_id, self.api_url)
        }

    def get_content(self, page_id: str) -> str:
        """Получение HTML-содержимого (для обратной совместимости)"""
        return self.get_page_full(page_id)['content']

    def get_time(self, page_id: str) -> str:
        """Получение даты последнего обновления"""
        url = f"{self.api_url}/rest/api/content/{page_id}"
        params = {'expand': 'version'}
        data = make_request(url, self.auth_token, params=params)
        return data['version'].get('when') or data['version'].get('createdAt')

    def get_page_url(self, page_id: str) -> str:
        """Формирует прямую ссылку на страницу"""
        return f"{self.api_url}/pages/viewpage.action?pageId={page_id}"
