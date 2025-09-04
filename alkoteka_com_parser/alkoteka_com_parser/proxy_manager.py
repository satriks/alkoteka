import os
import json
import random
import aiohttp
import asyncio
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class ProxyManager:
    def __init__(self, proxy_file=None):
        if proxy_file is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            proxy_file = os.path.join(current_dir, 'proxylist2.json')

        self.proxy_file = proxy_file
        self.working_proxy_file = os.path.join(current_dir, 'working_proxy.json')

        with open(self.proxy_file, 'r') as f:
            self.proxies = json.load(f)

        self.working_proxies = []
        self.banned_proxies = set()
        self.test_url = "https://alkoteka.com/"

        # Настройка сессии
        self.session = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504, 429],
            allowed_methods=['HEAD', 'GET', 'OPTIONS']
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.test_headers = {
            'Accept': 'application/json',
            'Referer': 'https://alkoteka.com/',
            'X-Requested-With': 'XMLHttpRequest'
        }

    async def test_proxy_async(self, proxy_data, session):
        proxy_str = f"http://{proxy_data['ip']}:{proxy_data['port']}"
        try:
            async with session.get(
                    self.test_url,
                    headers=self.test_headers,
                    proxy=proxy_str,
                    timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return proxy_data if data.get('success', False) else None
        except Exception as e:
            print(f"Proxy {proxy_str} failed: {str(e)}")
            return None

    async def check_proxies_async(self):
        connector = aiohttp.TCPConnector(limit=50)  # Ограничение одновременных соединений
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [self.test_proxy_async(proxy, session) for proxy in self.proxies]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            self.working_proxies = [result for result in results if result is not None]
            print(f"Found {len(self.working_proxies)} working proxies out of {len(self.proxies)}")

            # Сохраняем работающие прокси в файл
            with open(self.working_proxy_file, 'w') as f:
                json.dump(self.working_proxies, f, indent=2)
            print(f"Working proxies saved to {self.working_proxy_file}")

            return self.working_proxies

    def check_proxies(self):
        """Синхронный интерфейс для асинхронной проверки"""
        return asyncio.run(self.check_proxies_async())
    def test_proxy(self, proxy_data):
        proxy_str = f"http://{proxy_data['ip']}:{proxy_data['port']}"
        proxies = {
            'http': proxy_str,
            'https': proxy_str
        }

        try:
            response = self.session.get(
                self.test_url,
                headers=self.test_headers,
                proxies=proxies,
                timeout=15
            )

            # Проверяем успешный ответ API alkoteka.com
            if response.status_code == 200:
                try:
                    data = response.json()
                    return data.get('success', False)  # Проверяем success в ответе
                except json.JSONDecodeError:
                    return False
        except Exception as e:
            print(f"Proxy {proxy_str} failed with error: {str(e)}")
            return False
        return False

    def load_and_test_proxies(self):
        """Тестируем и загружаем только рабочие прокси"""
        print(f"Testing {len(self.proxies)} proxies...")

        # Тестируем и фильтруем прокси
        self.working_proxies = [
            proxy for proxy in self.proxies
            if self.test_proxy(proxy) and proxy['ip'] not in self.banned_proxies
        ]

        print(f"Found {len(self.working_proxies)} working proxies")

    def get_random_proxy(self):
        """Возвращает случайный рабочий прокси"""
        if not self.working_proxies:
            self.load_and_test_proxies()
            if not self.working_proxies:
                print("Warning: No working proxies available!")
                return None

        proxy = random.choice(self.working_proxies)
        return f"http://{proxy['ip']}:{proxy['port']}"

    def ban_proxy(self, proxy_url):
        """Добавляет прокси в бан-лист"""
        parsed = urlparse(proxy_url)
        if parsed.hostname:
            ip = parsed.hostname
            self.banned_proxies.add(ip)
            self.working_proxies = [
                p for p in self.working_proxies
                if p['ip'] != ip
            ]
            print(f"Banned proxy: {proxy_url}")

if __name__ == "__main__":
    prox = ProxyManager()
    prox.check_proxies()