# LMD-T-bot Web Interface

Локальный веб-интерфейс для просмотра данных по сделкам из SQLite базы данных.

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## Запуск сервера

```bash
python web/server.py
```

По умолчанию сервер запускается на `http://127.0.0.1:5000`

### Параметры командной строки

- `--host` - Хост для привязки (по умолчанию: 127.0.0.1)
- `--port` - Порт для запуска (по умолчанию: 5000)
- `--debug` - Включить режим отладки

Примеры:

```bash
# Запустить на порту 8080
python web/server.py --port 8080

# Запустить с доступом из локальной сети
python web/server.py --host 0.0.0.0 --port 5000

# Запустить в режиме отладки
python web/server.py --debug
```

## Структура проекта

```
web/
├── index.html      # Основная HTML страница
├── styles.css      # Стили интерфейса
├── app.js          # JavaScript логика клиента
├── server.py       # Flask сервер для API
└── README.md       # Документация
```

## API Endpoints

### GET `/api/trades`
Возвращает список всех сделок в формате JSON.

Пример ответа:
```json
{
  "success": true,
  "trades": [
    {
      "id": "order_id_123",
      "figi": "BBG004730N88",
      "direction": "buy",
      "price": 150.5,
      "quantity": 10,
      "status": "fill",
      "order_datetime": "2026-03-20T10:30:00",
      "instrument_name": "SBER",
      "average_position_price": 150.5,
      "executed_commission": 0.5,
      "initial_commission": 0.5,
      "executed_order_price": 150.5,
      "total_order_amount": 1505.0
    }
  ],
  "count": 1,
  "timestamp": "2026-03-20T11:00:00"
}
```

### GET `/api/stats`
Возвращает статистику по сделкам.

Пример ответа:
```json
{
  "success": true,
  "stats": {
    "total": 10,
    "filled": 8,
    "cancelled": 1,
    "rejected": 1,
    "total_volume": 15050.0,
    "total_commission": 25.5
  },
  "timestamp": "2026-03-20T11:00:00"
}
```

## База данных

По умолчанию используется файл `stats.db` в корневой директории проекта. Убедитесь, что база данных создана и содержит таблицу `orders`.

### Структура таблицы orders

```sql
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    figi TEXT,
    direction TEXT,
    price REAL,
    quantity INTEGER,
    status TEXT,
    order_datetime DATETIME,
    instrument_name TEXT,
    average_position_price REAL,
    executed_commission REAL,
    initial_commission REAL,
    executed_order_price REAL,
    total_order_amount REAL
)
```
