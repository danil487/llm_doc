# hybrid_search/confluence.py
import re
from typing import Tuple

from bs4 import BeautifulSoup, Tag

from hybrid_search.utils import make_request, initialize_auth, singleton, logger, extract_metadata_from_confluence, \
    Config


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
        page_info = {}
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
                if not isinstance(page, dict):
                    logger.warning(f"⚠️  Пропущен некорректный элемент page: {type(page)} = {page}")
                    continue

                page_id = page.get('id')
                if not page_id:
                    logger.warning(f"⚠️  Пропущена страница без ID: {page}")
                    continue

                page_id = str(page_id)
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
            Dict с полями: content (структурированный текст), structure_metadata, metadata
        """
        url = f"{self.api_url}/rest/api/content/{page_id}"
        params = {'expand': 'body.view,version,space,labels'}
        data = make_request(url, self.auth_token, params=params)

        html_content = data.get('body', {}).get('view', {}).get('value', '')
        structured_text, structure_meta = html_to_structured_text(html_content)

        return {
            'content': structured_text,
            'structure_metadata': structure_meta,
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


def html_table_to_markdown(table_tag: Tag) -> str:
    """Конвертирует HTML-таблицу в компактный Markdown"""
    rows = []

    header_row = table_tag.find('tr')
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td']) if th.get_text(strip=True)]
        if headers:
            rows.append("| " + " | ".join(headers) + " |")
            rows.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for tr in table_tag.find_all('tr')[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th']) if td.get_text(strip=True)]
        if cells:
            while len(cells) < len(rows[0].split('|')) - 2 if rows else 0:
                cells.append('')
            rows.append("| " + " | ".join(cells) + " |")

    return "\n".join(rows) if rows else ""


def html_code_to_markdown(code_tag: Tag) -> str:
    """Конвертирует блоки кода в Markdown"""
    code_text = code_tag.get_text()
    lang = code_tag.get('class', [''])[0] if code_tag.get('class') else ''
    lang = lang.replace('language-', '') if lang else ''
    return f"\n\n```{lang}\n{code_text.strip()}\n```\n\n"


def extract_headers_hierarchy(soup: BeautifulSoup, max_depth: int = 3) -> dict:
    """Извлекает иерархию заголовков для контекста"""
    headers = {}
    current_path = []

    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(tag.name[1])
        if level > max_depth:
            continue

        text = tag.get_text(strip=True)
        if not text:
            continue

        current_path = [p for p in current_path if p['level'] < level]
        current_path.append({'level': level, 'text': text})

        header_id = tag.get('id', '') or re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
        headers[header_id] = {
            'text': text,
            'level': level,
            'path': ' > '.join(p['text'] for p in current_path)
        }

    return headers


def html_to_structured_text(html_data: str) -> Tuple[str, dict]:
    """
    Конвертирует HTML в структурированный текст с сохранением:
    - Таблиц → Markdown
    - Кода → Markdown code blocks
    - Заголовков → контекстная иерархия
    - Списков → маркеры

    Returns:
        tuple: (structured_text, metadata)
    """
    if not html_data:
        return "", {}

    soup = BeautifulSoup(html_data, 'html.parser')
    headers_meta = extract_headers_hierarchy(soup, Config.MAX_HEADER_DEPTH)

    # Конвертируем таблицы в Markdown
    for table in soup.find_all('table'):
        md_table = html_table_to_markdown(table)
        if md_table:
            table.replace_with(f"\n\n{md_table}\n\n")
        else:
            table.decompose()

    # Конвертируем блоки кода
    for code in soup.find_all(['pre', 'code']):
        md_code = html_code_to_markdown(code)
        code.replace_with(md_code)

    # Сохраняем структуру заголовков и списков
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        tag.insert_before('\n## ')
        tag.insert_after('\n')

    for ul in soup.find_all('ul'):
        ul.insert_before('\n')
        ul.insert_after('\n')
    for ol in soup.find_all('ol'):
        ol.insert_before('\n')
        ol.insert_after('\n')
    for li in soup.find_all('li'):
        li.insert_before('• ')
        li.append('\n')

    # Убираем шум
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
        tag.decompose()

    # Добавляем разделители между параграфами
    for p in soup.find_all('p'):
        p.append('\n\n')

    # Извлекаем текст
    text = soup.get_text(separator=' ', strip=True)

    # Чистим лишние переносы
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    metadata = {
        'headers': headers_meta,
        'has_tables': bool(soup.find('table')),
        'has_code': bool(soup.find(['pre', 'code'])),
        'word_count': len(text.split())
    }

    return text.strip(), metadata
