# InfraGIS

InfraGIS — веб-приложение для отображения результатов диагностики автомобильных дорог.

MVP включает:
- вход по логину/паролю (JWT),
- роли `admin` и `viewer`,
- карту с подложкой OpenStreetMap,
- загрузку и управление слоями GeoJSON только администратором,
- иерархию дорожных слоёв (`road` -> `road_axis` / `iri` / `defects`),
- загрузку оси дороги из GeoJSON/CSV/ZIP Shapefile,
- расчет километража (chainage) по геометрии оси.
- модуль 360 с геопривязкой кадров и линейной привязкой к оси (`axis_km`).

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
- `GET /layers/tree` — дерево слоёв (parent-child)
- `POST /layers/roads` — создать верхнеуровневый слой дороги (`kind=road`)
- `POST /layers` — добавить слой (только admin; multipart с файлом GeoJSON или `source_url`)
- `POST /layers/{road_id}/axis` — загрузить ось дороги в выбранную дорогу (GeoJSON/CSV/ZIP Shapefile)
- `POST /layers/iri-records` — добавить запись IRI с км-привязкой
- `GET /layers/iri-records/{layer_id}` — список записей IRI слоя
- `POST /layers/defect-records` — добавить запись дефекта с км-привязкой
- `GET /layers/defect-records/{layer_id}` — список записей дефектов слоя
- `GET /layers/{id}/geojson` — данные слоя
- `PATCH /layers/{id}` — обновить метаданные слоя (только admin)
- `DELETE /layers/{id}` — удалить слой (только admin)
- `GET /admin/users` — список пользователей (только admin)
- `POST /admin/users` — создать пользователя (только admin)
- `POST /media360/items/{media_id}/geolink` — создать геопривязку 360-точки (поддерживает `axis_layer_id`, вычисляет `axis_km`)
- `GET /media360/map-points` — список 360-точек на карте (фильтр `layer_id` / `axis_layer_id`)
- `POST /media360/axis/{axis_layer_id}/recalculate-km` — массово пересчитать `axis_km` для существующих geolink (только admin)

## Формат загрузки слоя

Поддерживается GeoJSON:
- `FeatureCollection`
- `Feature`
- геометрии (`Point`, `LineString`, `Polygon`, `Multi*`, `GeometryCollection`)

## Дорожная модель (этап 1)

### Иерархия слоёв

- `road` — контейнер дороги (верхний уровень дерева)
- `road_axis` — ось дороги (линейная геометрия)
- `iri` — тематический слой данных продольной ровности
- `defects` — тематический слой дефектов покрытия

Технические поля:
- `parent_id` — родительский слой в дереве
- `axis_layer_id` — ссылка на ось для линейной привязки тематических записей

### Импорт оси дороги

Поддерживаемые форматы:
- `GeoJSON` (`LineString`, `MultiLineString`, `Feature`, `FeatureCollection`)
- `CSV` (минимум `lon`/`lat`, опционально `order`/`seq`/`index`)
- `ZIP Shapefile` (обязательные файлы: `.shp`, `.shx`, `.dbf`)

После загрузки ось нормализуется и сохраняется как GeoJSON, далее вычисляется километраж:
- на выходе endpoint-а `/layers/{road_id}/axis` возвращаются:
  - `total_km` — суммарная длина оси
  - `points[]` — вершины оси с накопленным `km`

### Диагностические записи

- IRI и дефекты хранятся как отдельные записи, привязанные к:
  - тематическому слою (`layer_id`)
  - оси дороги (`axis_layer_id`)
  - диапазону километража (`km_start`, `km_end`)

Это создает основу для дальнейшей визуализации, фильтрации и отчетности по нормативам ОДМ/ГОСТ.

### Связка с модулем 360

- В `media_geo_links` добавлены поля:
  - `axis_layer_id` — ось дороги для линейной привязки кадра
  - `axis_km` — километраж точки по оси
- При создании geolink через `/media360/items/{media_id}/geolink`:
  - ось можно передать явно (`axis_layer_id`) или получить косвенно через `layer_id`
  - backend вычисляет ближайшую проекцию точки на ось и сохраняет `axis_km`
- Для обновления старых привязок после изменения оси доступен bulk endpoint:
  - `POST /media360/axis/{axis_layer_id}/recalculate-km`
  - опционально `?media_id=<id>` для пересчета одного медиа

## Тесты

```powershell
cd c:\Users\asp1r\InfraGIS\backend
py -m pytest tests -q
```

Тесты покрывают базовые сценарии:
- аутентификация,
- проверка доступа по ролям,
- создание/чтение слоёв,
- создание дерева слоёв дорог,
- импорт оси в форматах GeoJSON/CSV/ZIP Shapefile,
- расчет километража по оси,
- сохранение записей IRI и дефектов,
- связку 360-точки с осью и расчет `axis_km`,
- массовый пересчет `axis_km` по оси.
