import scrapy
import json
from urllib.parse import urlencode
from datetime import datetime
from ..proxy_manager import ProxyManager


class AlkotekaBlogSpider(scrapy.Spider):
    name = 'spider_name'
    allowed_domains = ['alkoteka.com']

    custom_settings = {
        'DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS': 1,
        'FEEDS': {
            'alkoteka_blog.json': {
                'format': 'json',
                'encoding': 'utf8',
                'indent': 4,
                'overwrite': True,
            }
        },
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'ROBOTSTXT_OBEY': True,
        'HTTPERROR_ALLOW_ALL': True,
        'LOG_LEVEL': 'INFO',
    }

    '''
    Для работы с прокси включить use_proxy=True (Перед запуском настроить список прокси в proxy_manager.py)
    '''
    use_proxy = False  # Включение прокси

    params = {
        'city_uuid': '4a70f9e0-46ae-11e7-83ff-00155d026416',  # Указывает на регион Краснодар, код взят из запросов к сайту
        'per_page': 100,
        'page': 1,
        'root_category_slug': ''
    }

    start_urls = [
        "https://alkoteka.com/catalog/bezalkogolnye-napitki-1",
        "https://alkoteka.com/catalog/slaboalkogolnye-napitki-2",
        "https://alkoteka.com/catalog/axioma-spirits"
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'use_proxy' in kwargs:
            self.use_proxy = kwargs['use_proxy'].lower() == 'true'

        self.active_proxies = []
        if self.use_proxy:
            self.proxy_manager = ProxyManager()
            self.logger.info("Proxy support ENABLED")
        else:
            self.logger.info("Proxy support DISABLED")

    async def start(self):
        """Основная точка входа"""
        if self.use_proxy:
            self.active_proxies = await self.proxy_manager.load_and_test_proxies()

        # Генерация начальных запросов
        for url in self.start_urls:
            request = await self.create_initial_request(url)
            if request:
                yield request

    async def create_initial_request(self, url):
        """Создание начального запроса"""
        slug = url.split("/")[-1]
        self.params['root_category_slug'] = slug
        api_url = f"https://alkoteka.com/web-api/v1/product?{urlencode(self.params)}"

        meta = {
            'handle_httpstatus_all': True,
            'slug': slug,
            'dont_obey_robotstxt': False
        }

        if self.use_proxy and self.active_proxies:
            meta['proxy'] = self.proxy_manager.get_random_proxy()

        return scrapy.Request(
            api_url,
            headers=self.get_api_headers(),
            callback=self.parse,
            meta=meta,
            errback=self.handle_proxy_error if self.use_proxy else None,
            dont_filter=True
        )

    def parse(self, response):
        """Разбор основного API ответа"""
        try:
            data = response.json()
            if not data.get('success'):
                raise ValueError(f"API error: {data.get('message')}")

            # Обработка результатов
            for item in data.get('results', []):
                yield from self.process_item(item)

            # Пагинация
            if data.get('meta', {}).get('has_more_pages', False):
                yield from self.handle_pagination(response.url, data['meta'])

        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Error parsing response: {str(e)}")

    def process_item(self, item):
        """Обработка одного элемента"""
        detail_url = self.get_detail_url(item)
        yield scrapy.Request(
            detail_url,
            headers={'Accept': 'application/json'},
            meta={'product_data': self.extract_base_product_data(item)},
            callback=self.parse_product_detail
        )

    def handle_pagination(self, current_url, meta):
        """Обработка пагинации"""
        self.params['page'] = meta.get('current_page', 1) + 1
        next_url = f"{current_url.split('?')[0]}?{urlencode(self.params)}"

        yield scrapy.Request(
            next_url,
            headers=self.get_api_headers(),
            callback=self.parse,
            meta={'proxy': self.proxy_manager.get_random_proxy()} if self.use_proxy else {},
            errback=self.handle_proxy_error if self.use_proxy else None,
            dont_filter=True
        )

    def handle_proxy_error(self, failure):
        """Обработка ошибок прокси"""
        self.logger.error(f"Proxy error: {failure.value}")

        if hasattr(failure, 'request') and failure.request:
            request = failure.request
            banned_proxy = request.meta.get('proxy')

            if banned_proxy and self.use_proxy:
                self.active_proxies = [p for p in self.active_proxies if p != banned_proxy]
                self.logger.warning(f"Banned proxy: {banned_proxy}")

            # Повтор запроса
            new_request = request.replace(
                meta={**request.meta, 'proxy': self.proxy_manager.get_random_proxy()},
                dont_filter=True
            )
            return new_request

    def parse_product_detail(self, response):
        """Разбор детальной информации о продукте"""
        try:
            data = response.json()
            if not data.get('success'):
                raise ValueError(f"API error: {data.get('message')}")

            product_data = response.meta['product_data']
            yield {
                **product_data,
                **self.extract_product_details(data['results'])
            }
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Error parsing product detail: {str(e)}")

    def get_api_headers(self):
        return {
            'Accept': 'application/json',
            'Referer': 'https://alkoteka.com/',
            'X-Requested-With': 'XMLHttpRequest'
        }

    def get_detail_url(self, item):
        slug = item.get('slug', '')
        if not slug:
            slug = f"{item.get('name', '').lower().replace(' ', '-')}_{item.get('vendor_code', '')}"
        return f"https://alkoteka.com/web-api/v1/product/{slug}?city_uuid={self.params['city_uuid']}"

    def extract_base_product_data(self, item):
        return {
            'timestamp': int(datetime.now().timestamp()),
            'RPC': item.get('uuid', ''),
            'url': item.get('product_url', ''),
            'title': item.get('name', ''),
            'marketing_tags': self.get_marketing_tags(item)
        }

    def get_marketing_tags(self, item):
        return [
            tag['title'] for tag in item.get('action_labels', [])
            if tag.get('title')
        ] + [
            fltr['title'] for fltr in item.get('filter_labels', [])
            if fltr.get('title') and fltr.get('filter') != 'obem'
        ]

    def extract_product_details(self, product):
        brand = next((
            block['values'][0]['name'] for block in product.get('description_blocks', [])
            if block.get('title') == 'Бренд' and block.get('values')
        ), None)

        return {
            'brand': brand,
            'section': self.get_breadcrumbs(product.get('category', {})),
            'price_data': self.get_price_data(product),
            'stock': {
                'in_stock': product.get('available', False),
                'count': product.get('quantity_total', 0)
            },
            'assets': {
                'main_image': product.get('image_url')
            },
            'metadata': product
        }

    def get_price_data(self, product):
        current_price = int(product.get('price', 0))
        try:
            original_price = product.get('prev_price', 0)
            original_price = int(original_price) if original_price else 0
        except (KeyError, TypeError) :
            original_price = 0

        price_data = {
            'current': current_price,
            'original': original_price
        }

        if original_price > current_price:
            discount = round((original_price - current_price) / original_price * 100, 1)
            price_data['sale_tag'] = f"Скидка {discount}%"

        return price_data

    def get_breadcrumbs(self, category):
        breadcrumbs = []

        def collect_parents(cat):
            if cat.get('parent'):
                collect_parents(cat['parent'])
            if cat.get('name'):
                breadcrumbs.append(cat['name'])

        try:
            if category:
                collect_parents(category)
        except RecursionError:
            self.logger.warning("Category hierarchy too deep")

        return breadcrumbs
