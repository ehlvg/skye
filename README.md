# Telegram OpenRouter Bot

Telegram бот на Python с интеграцией OpenRouter API, поддержкой Telegram Stars платежей и базой данных Supabase.

## Возможности

- 🤖 Интеграция с OpenRouter API для доступа к различным AI моделям
- 💬 Поддержка контекстных диалогов
- 🎯 Кастомные системные промпты
- 📄 Обработка PDF документов и изображений
- � Поиск в интернете (Plus тариф)
- �💳 Платежи через Telegram Stars
- 📊 Система лимитов и тарифов (Lite/Plus)
- 🗄️ Безопасная база данных Supabase
- 🐳 Docker поддержка
- 🔄 Автоматическое масштабирование

## Требования

- Python 3.11+
- Telegram Bot Token
- OpenRouter API ключ
- Supabase проект и API ключи
- Docker (опционально)

## Установка

### Обычная установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd telegram-openrouter-bot
```

2. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Скопируйте `.env.example` в `.env` и заполните переменные:
```bash
cp .env.example .env
```

5. Настройте переменные окружения в `.env`:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
SUPABASE_URL=your_supabase_url_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here
SUBSCRIPTION_PRICE_STARS=300
CONTEXT_SIZE=10
```

6. Запустите бота:
```bash
python bot.py
```

### Docker установка

1. Создайте `.env` файл как описано выше

2. Запустите через Docker Compose:
```bash
docker-compose up -d
```

3. Проверьте логи:
```bash
docker-compose logs -f telegram-bot
```

## Настройка Supabase

1. Создайте новый проект в [Supabase](https://supabase.com)
2. Получите URL проекта и Service Role Key
3. Таблицы создадутся автоматически при первом запуске

## Команды бота

- `/start` - Приветственное сообщение
- `/ask <вопрос>` - Задать вопрос AI (поддерживает файлы)
- `/search <запрос>` - Поиск в интернете (только Plus)
- `/profile` - Посмотреть профиль и лимиты
- `/upgrade` - Обновиться до Plus тарифа
- `/model` - Выбрать AI модель
- `/setprompt <промпт>` - Установить системный промпт
- `/getprompt` - Показать текущий промпт
- `/resetprompt` - Сбросить промпт
- `/resetcontext` - Очистить контекст диалога

### Особенности поиска

Команда `/search` использует специальную модель `google/gemini-2.5-flash:online`, которая автоматически выполняет поиск в интернете для получения актуальной информации. Эта функция доступна только пользователям Plus тарифа и поддерживает:

- Текстовые запросы
- Изображения с поисковыми запросами
- PDF документы с поисковыми запросами

## Тарифы

### Lite (бесплатный)
- 10 сообщений в день
- 50 сообщений в месяц
- Доступ к базовым моделям

### Plus (300 Telegram Stars)
- 50 сообщений в день
- 500 сообщений в месяц
- Доступ к премиум моделям
- 🔍 Поиск в интернете (/search)
- Срок действия: 30 дней

## Поддерживаемые файлы

- PDF документы
- Изображения (JPG, PNG, WebP)

## Мониторинг

Логи доступны через Docker:
```bash
docker-compose logs -f telegram-bot
```

## Безопасность

- Использование Service Role Key для Supabase
- Хранение данных в зашифрованном виде
- Лимиты на запросы
- Валидация файлов

## Обновления

```bash
git pull
docker-compose down
docker-compose up -d --build
```

## Поддержка

Если у вас есть вопросы или проблемы, создайте issue в репозитории. 