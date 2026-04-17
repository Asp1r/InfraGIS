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
  - `Layer` — метаданные слоя, тип источника (файл/URL), тип дорожного слоя, parent-child структура, ссылка на создателя.  
  - `IriMeasurement` — записи продольной ровности с линейной привязкой (`km_start`/`km_end`).
  - `DefectRecord` — записи дефектов с линейной привязкой и нормативной ссылкой.
  - `MediaGeoLink` — геопривязка 360-медиа, включая `axis_layer_id` и расчетный `axis_km`.
  Enum-типы:
  - `UserRole`: `admin`, `viewer`
  - `LayerSourceType`: `uploaded_geojson`, `url_geojson`
  - `LayerKind`: `road`, `road_axis`, `iri`, `defects`

- `app/schemas.py`  
  Pydantic-схемы для валидации входа/выхода API (`LoginRequest`, `Token`, `UserCreate`, `LayerOut` и т.д.), включая:
  - дерево слоёв (`LayerTreeNode`),
  - upload оси с chainage (`AxisUploadOut`),
  - схемы IRI/дефектов.
  - схемы media-линейной привязки (`axis_layer_id`, `axis_km`) и ответ bulk-пересчета.

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
  - `GET /layers/tree` — дерево слоев (иерархия по `parent_id`).
  - `POST /layers/roads` — создание корневого слоя `Дорога`.
  - `POST /layers` — создание слоя (файл GeoJSON или URL).
  - `POST /layers/{road_id}/axis` — загрузка оси дороги (GeoJSON/CSV/ZIP Shapefile) в выбранную дорогу.
  - `POST /layers/from-url` — JSON-версия создания слоя из URL.
  - `POST /layers/iri-records` / `GET /layers/iri-records/{layer_id}` — работа с IRI.
  - `POST /layers/defect-records` / `GET /layers/defect-records/{layer_id}` — работа с дефектами.
  - `PATCH /layers/{id}` — изменить имя/описание слоя.
  - `DELETE /layers/{id}` — удалить слой и локальный файл, если был upload.
  - `GET /layers/{id}/geojson` — вернуть GeoJSON из файла или проксировать с URL.
  
  Важный момент: перед сохранением проверяется базовая валидность GeoJSON (`_validate_geojson`).
  Для оси добавлена нормализация входного формата и расчет километража.

- `app/services/import_axis.py`  
  Сервис импорта оси дороги:
  - парсинг GeoJSON,
  - парсинг CSV с lon/lat,
  - парсинг ZIP Shapefile (`.shp/.shx/.dbf`),
  - нормализация геометрии к `LineString`/`MultiLineString`.

- `app/services/chainage.py`  
  Сервис линейной привязки:
  - расчет длины по сегментам (Haversine),
  - расчет накопленного километража по вершинам оси,
  - выдача `total_km` и `points[]`.

- `app/services/linear_reference.py`
  Сервис привязки произвольной точки к оси дороги:
  - проектирование точки на ближайший сегмент оси,
  - вычисление chainage в км (`axis_km`) от начала оси.

- `app/routers/media360.py`
  Расширен для дорожной линейной привязки:
  - `POST /media360/items/{media_id}/geolink` теперь поддерживает `axis_layer_id` и сохраняет `axis_km`,
  - `GET /media360/map-points` возвращает `axis_km` и поддерживает фильтр `axis_layer_id`,
  - `POST /media360/axis/{axis_layer_id}/recalculate-km` выполняет массовый пересчет километража для существующих geolink.

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

- `alembic/versions/002_road_model.py`  
  Миграция дорожной модели:
  - добавляет `layerkind`,
  - добавляет `layers.parent_id` и `layers.axis_layer_id`,
  - создает таблицы `iri_measurements` и `defect_records`,
  - индексы/внешние ключи для быстрых выборок и ссылочной целостности.

- `alembic/versions/005_media_geolink_axis_chainage.py`
  Миграция для связки 360 и дорожной оси:
  - добавляет `media_geo_links.axis_layer_id`,
  - добавляет `media_geo_links.axis_km`,
  - добавляет индекс и внешний ключ на ось.

### 2.5 Тесты

- `tests/conftest.py`  
  Фикстуры для тестов (in-memory SQLite, тестовые клиенты, подмена dependency).
- `tests/test_auth.py`  
  Проверяет login/me и ограничения ролей.
- `tests/test_layers.py`  
  Проверяет авторизацию слоя, upload GeoJSON и чтение слоя, а также:
  - создание дерева дорог,
  - загрузку оси в форматах GeoJSON/CSV/ZIP Shapefile,
  - создание записей IRI/дефектов.
- `tests/test_chainage.py`
  Проверяет корректность расчета километража для `LineString` и `MultiLineString`.
- `tests/test_media360.py`
  Дополнительно покрывает:
  - расчет `axis_km` при создании geolink,
  - массовый пересчет `axis_km`,
  - проверку прав доступа к bulk endpoint (только admin).

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
  Дополнительно поддержаны вызовы API дорожного дерева и оси.

- `src/types.ts`  
  Общие типы `User`, `Layer`, `UserRole`, а также:
  - `LayerKind`,
  - `LayerTreeNode`,
  - `AxisUploadResult`,
  - типы записей IRI/дефектов.

### 3.4 UI-страницы

- `src/pages/LoginPage.tsx`  
  Форма входа, сохраняет JWT через `setToken`.

- `src/pages/MapPage.tsx`  
  Загружает дерево слоев (`/layers/tree`), хранит состояние включенных слоев, группирует отображение по дорогам и передает данные в `MapView`.

- `src/components/MapView.tsx`  
  Карта MapLibre:
  - OSM как raster basemap,
  - для каждого включенного слоя добавляет GeoJSON source + fill/line layer,
  - удаляет отключенные слои,
  - загружает GeoJSON через backend endpoint `/layers/{id}/geojson`.
  
  Дополнительно:
  - отдельная стилизация оси дороги (`road_axis`) с визуальным приоритетом,
  - сохранена интеграция с модулем точек 360,
  - popup 360-точек показывает километраж (`axis_km`), если он рассчитан.

- `src/pages/AdminUsersPage.tsx`  
  Список пользователей и форма создания нового пользователя.

- `src/pages/AdminLayersPage.tsx`  
  Страница управления дорожными слоями:
  - создание слоя `Дорога`,
  - загрузка оси в выбранную дорогу (GeoJSON/CSV/ZIP),
  - автосоздание дочерних тематических слоев `IRI` и `Дефекты`,
  - удаление слоев.

- `src/layout/AppLayout.tsx`  
  Общая навигация + кнопка logout.

- `src/index.css`  
  Базовые стили приложения.

## 4) Поток данных (от пользователя до карты)

1. Пользователь логинится на `/login`.
2. Backend возвращает JWT.
3. Frontend хранит токен и вызывает `/auth/me`.
4. На карте вызывается `/layers/tree`, пользователь видит дороги и вложенные тематические слои.
5. Администратор создает `Дорогу` и загружает `Ось дороги` через `/layers/{road_id}/axis`.
6. Backend нормализует ось и считает километраж (`total_km`, `points[]`).
7. IRI и дефекты сохраняются как линейно-привязанные записи к этой оси.
8. При включении слоя фронтенд запрашивает `/layers/{id}/geojson`.
9. `MapView` добавляет source/layers в MapLibre.
10. При создании geolink 360 backend вычисляет `axis_km` по оси (если axis задан/разрешен из контекста слоя).
11. При необходимости admin массово пересчитывает `axis_km` через `/media360/axis/{axis_layer_id}/recalculate-km`.
12. Если пользователь admin — доступны страницы управления пользователями и слоями.

## 5) Что важно помнить при дальнейшей разработке

- Любые изменения схемы БД делать через новые миграции Alembic.
- Не хранить секреты в git: только в `.env` на сервере.
- Для production лучше раздавать фронтенд из `/var/www/...`, а не напрямую из `/home/...`.
- Для повышения надежности можно добавить refresh-token flow и ограничение попыток login.
