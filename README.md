 ## Парсер Alkoteka - Scrapy Spider

  ### Установка необходимых компонентов
  1. Рекомендуется создать виртуальное окружение:

  ```
  python -m venv venv
  source venv/bin/activate  # Linux/Mac
  venv\Scripts\activate     # Windows
  ```

 2. Установите зависимости:
   ```
   pip install -r .\requirements.txt  
   ```
Структура проекта
```
alkoteka_com_parser/
├── spiders/
│   └── alkoteka_v3.py
├── proxy_manager.py
├── proxies.json        # Создайте этот файл
└── scrapy.cfg
```
### 🚀 Запуск парсера
#### Базовый запуск (без прокси):

```
scrapy crawl spider_name -O result.json

```
#### С использованием прокси:
 1. Создайте файл proxylist.json в корне проекта:
  ```json
[
  "http://user:pass@proxy1.com:8000",
  "http://user:pass@proxy2.com:8080"
]

```
2. Запустите с включенными прокси:
Настройка прокси
Создайте файл proxies.json:
JSON
[
  "http://username:password@proxy1:port",
  "http://username:password@proxy2:port"
]
```
scrapy crawl spider_name -O result.json -a use_proxy=true

```
