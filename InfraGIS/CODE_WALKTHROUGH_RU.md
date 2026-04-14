# InfraGIS: подробный разбор исходного кода

Этот документ объясняет, что делает каждый ключевой файл проекта и как данные проходят через систему.

## 1) Корневой уровень

- `docker-compose.yml`  
  Поднимает PostgreSQL с PostGIS (`db`) для локальной разработки и тестового стенда.
- `.gitignore`  
  Исключает временные файлы, артефакты сборки и локальные директории загрузок (`backend/uploads`, `backend/uploads_test`).
- `README.md`  
  Инструкция по запуску и список основных API.

## 2) Backend (`backend/`)

### 2.1 Конфигурация и БД

- `app/config.py`  
  Централизованные настройки приложения через переменные окружения (`DATABASE_URL`, `JWT_SECRET`, CORS, upload path).  
  Класс `Settings` автоматически читает `.env`.

- `app/database.py`  
  Создает SQLAlchemy `engine`, фабрику сессий `SessionLocal` и базовый класс `Base` для моделей.  
  Функция `get_db()` отдает сессию БД для FastAPI dependency injection.

- `app/models.py`  
  ORM-модели:
  - `User` — логин, хэш пароля, роль, активность, дата создания.
  - `Layer` — метаданные слоя, тип источника (файл/URL), ссылка на создателя.  
  Enum-типы:
  - `UserRole`: `admin`, `viewer`
  - `LayerSourceType`: `uploaded_geojson`, `url_geojson`

- `app/schemas.py`  
  Pydantic-схемы для валидации входа/выхода API (`LoginRequest`, `Token`, `UserCreate`, `LayerOut` и т.д.).

### 2.2 Безопасность и авторизация

- `app/security.py`  
  - Хэширование паролей (`hash_password`) и проверка (`verify_password`) через `passlib`.
  - Генерация и декод JWT (`create_access_token`, `decode_token`).

- `app/deps.py`  
  - `get_current_user` читает `Bearer` токен, извлекает `sub` (ID пользователя), достает пользователя из БД.
  - `require_admin` пропускает только пользователей с ролью `admin`.

- `app/bootstrap.py`  
  При старте приложения может создать первого администратора из `.env` (`ADMIN_LOGIN`, `ADMIN_PASSWORD`), если в БД нет admin.

### 2.3 API-роутеры

- `app/routers/auth.py`  
  - `POST /auth/login` — проверка логина/пароля, выдача JWT.
  - `GET /auth/me` — вернуть текущего пользователя.

- `app/routers/admin.py`  
  Доступ только для admin:
  - `GET /admin/users` — список пользователей.
  - `POST /admin/users` — создание нового пользователя.

- `app/routers/layers.py`  
  Основная логика слоев:
  - `GET /layers` — список слоев.
  - `POST /layers` — создание слоя (файл GeoJSON или URL).
  - `POST /layers/from-url` — JSON-версия создания слоя из URL.
  - `PATCH /layers/{id}` — изменить имя/описание слоя.
  - `DELETE /layers/{id}` — удалить слой и локальный файл, если был upload.
  - `GET /layers/{id}/geojson` — вернуть GeoJSON из файла или проксировать с URL.
  
  Важный момент: перед сохранением проверяется базовая валидность GeoJSON (`_validate_geojson`).

- `app/main.py`  
  Точка входа FastAPI:
  - Lifespan-хук создает upload-папку и выполняет bootstrap admin.
  - Подключает CORS middleware.
  - Регистрирует роутеры `auth`, `admin`, `layers`.
  - Health endpoint: `GET /health`.

### 2.4 Миграции

- `alembic/env.py` и `alembic.ini`  
  Конфигурация Alembic.

- `alembic/versions/001_initial.py`  
  Первая миграция:
  - включает расширение PostGIS,
  - создает таблицы `users` и `layers`,
  - создает index на `users.login`.  
  
  Исправление после реального деплоя: убрано двойное создание enum-типа в `upgrade()`.

### 2.5 Тесты

- `tests/conftest.py`  
  Фикстуры для тестов (in-memory SQLite, тестовые клиенты, подмена dependency).
- `tests/test_auth.py`  
  Проверяет login/me и ограничения ролей.
- `tests/test_layers.py`  
  Проверяет авторизацию слоя, upload GeoJSON и чтение слоя.

## 3) Frontend (`frontend/`)

### 3.1 Инфраструктура

- `package.json`  
  Зависимости React/MapLibre и скрипты (`dev`, `build`, `preview`).  
  Добавлен `@types/geojson` для строгой типизации данных источника карты.

- `vite.config.ts`  
  Конфиг Vite + dev proxy к backend (`/auth`, `/admin`, `/layers`, `/health`).

- `tsconfig*.json`  
  Настройки TypeScript.

### 3.2 Точка входа и авторизация

- `src/main.tsx`  
  Инициализирует React-приложение, роутер и AuthProvider.

- `src/auth/AuthContext.tsx`  
  Хранит токен и текущего пользователя в контексте, поддерживает:
  - `setToken`,
  - `refreshMe`,
  - `logout`.

- `src/App.tsx`  
  Маршрутизация:
  - `/login`,
  - `/` (карта),
  - `/admin/users`, `/admin/layers` (только admin).  
  Компоненты `Protected` и `AdminOnly` защищают доступ.

### 3.3 API и типы

- `src/api.ts`  
  Обертки над `fetch`:
  - `apiFetch` для JSON-запросов,
  - `apiUpload` для multipart upload.  
  Автоматически добавляет `Authorization: Bearer ...`, если токен есть в `localStorage`.

- `src/types.ts`  
  Общие типы `User`, `Layer`, `UserRole`.

### 3.4 UI-страницы

- `src/pages/LoginPage.tsx`  
  Форма входа, сохраняет JWT через `setToken`.

- `src/pages/MapPage.tsx`  
  Загружает список слоев, хранит состояние включенных слоев, передает его в `MapView`.

- `src/components/MapView.tsx`  
  Карта MapLibre:
  - OSM как raster basemap,
  - для каждого включенного слоя добавляет GeoJSON source + fill/line layer,
  - удаляет отключенные слои,
  - загружает GeoJSON через backend endpoint `/layers/{id}/geojson`.
  
  Исправление после real-world сборки: `apiFetch<GeoJSON.GeoJSON>` вместо `apiFetch<object>`.

- `src/pages/AdminUsersPage.tsx`  
  Список пользователей и форма создания нового пользователя.

- `src/pages/AdminLayersPage.tsx`  
  Список слоев, форма загрузки файла или URL, удаление слоя.

- `src/layout/AppLayout.tsx`  
  Общая навигация + кнопка logout.

- `src/index.css`  
  Базовые стили приложения.

## 4) Поток данных (от пользователя до карты)

1. Пользователь логинится на `/login`.
2. Backend возвращает JWT.
3. Frontend хранит токен и вызывает `/auth/me`.
4. На карте вызывается `/layers`, пользователь видит список слоев.
5. При включении слоя фронтенд запрашивает `/layers/{id}/geojson`.
6. `MapView` добавляет source/layers в MapLibre.
7. Если пользователь admin — доступны страницы управления пользователями и слоями.

## 5) Что важно помнить при дальнейшей разработке

- Любые изменения схемы БД делать через новые миграции Alembic.
- Не хранить секреты в git: только в `.env` на сервере.
- Для production лучше раздавать фронтенд из `/var/www/...`, а не напрямую из `/home/...`.
- Для повышения надежности можно добавить refresh-token flow и ограничение попыток login.
