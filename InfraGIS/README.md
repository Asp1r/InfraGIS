# InfraGIS

InfraGIS — веб-приложение для отображения результатов диагностики автомобильных дорог.

MVP включает:
- вход по логину/паролю (JWT),
- роли `admin` и `viewer`,
- карту с подложкой OpenStreetMap,
- загрузку и управление слоями GeoJSON только администратором.

## Структура

- `backend/` — FastAPI API, Alembic миграции, тесты.
- `frontend/` — React + TypeScript + Vite + MapLibre.
- `docker-compose.yml` — PostgreSQL/PostGIS.

## Быстрый старт

### 1) База данных (PostGIS)

```powershell
cd c:\Users\asp1r\InfraGIS
docker compose up -d
```

### 2) Backend

```powershell
cd c:\Users\asp1r\InfraGIS\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
copy .env.example .env
py -m alembic upgrade head
py -m uvicorn app.main:app --reload --port 8000
```

По умолчанию первый администратор создаётся автоматически из `.env`:
- `ADMIN_LOGIN`
- `ADMIN_PASSWORD`

Если эти поля пустые, автосоздание не выполняется.

### 3) Frontend

```powershell
cd c:\Users\asp1r\InfraGIS\frontend
npm install
npm run dev
```

Открыть: `http://localhost:5173`

## Основные API

- `POST /auth/login` — вход
- `GET /auth/me` — текущий пользователь
- `GET /layers` — список слоёв (авторизованный пользователь)
- `POST /layers` — добавить слой (только admin; multipart с файлом GeoJSON или `source_url`)
- `GET /layers/{id}/geojson` — данные слоя
- `PATCH /layers/{id}` — обновить метаданные слоя (только admin)
- `DELETE /layers/{id}` — удалить слой (только admin)
- `GET /admin/users` — список пользователей (только admin)
- `POST /admin/users` — создать пользователя (только admin)

## Формат загрузки слоя

Поддерживается GeoJSON:
- `FeatureCollection`
- `Feature`
- геометрии (`Point`, `LineString`, `Polygon`, `Multi*`, `GeometryCollection`)

## Тесты

```powershell
cd c:\Users\asp1r\InfraGIS\backend
py -m pytest tests -q
```

Тесты покрывают базовые сценарии:
- аутентификация,
- проверка доступа по ролям,
- создание/чтение слоёв.
