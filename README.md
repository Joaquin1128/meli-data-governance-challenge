# MELI Enriched Products API

![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-cache--aside-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![Architecture](https://img.shields.io/badge/architecture-hexagonal-6E56CF)

Solución para el *Data Governance: Desafío Técnico* de Mercado Libre. Enriquece
descripciones de producto con IA y las expone a través de una API RESTful de solo
lectura, pensada para ser consumida por un sistema de recomendación u otras
entidades externas.

El proyecto tiene dos componentes independientes:

1. **Pipeline de extracción y enriquecimiento** (`notebooks/meli_enrichment_pipeline.ipynb`,
   pensado para correr en Google Colab): extrae productos de la API de MercadoLibre
   (`/products/search`, OAuth2), genera descripciones enriquecidas con Gemini para los
   ítems que lo necesitan, y persiste todo en SQLite.
2. **API RESTful** (`src/meli_api/`, FastAPI): sirve esos datos ya enriquecidos, con
   arquitectura hexagonal, cache-aside sobre Redis con circuit breaker, rate limiting,
   y observabilidad (logs estructurados, métricas Prometheus, health check).

La API **no llama a MercadoLibre ni a Gemini en tiempo real**: solo lee lo que el
pipeline offline ya dejó en `meli_products.db`. El detalle de esta decisión y del
resto del diseño está en [`docs/architecture.md`](docs/architecture.md).

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/informe.md`](docs/informe.md) | Informe del desafío: decisiones, desafíos encontrados, resultados de corridas reales del pipeline, e impacto del enriquecimiento en el sistema de recomendación. |
| [`docs/architecture.md`](docs/architecture.md) | Arquitectura de la API: capas, puertos, estrategia de resiliencia y observabilidad, diseño pensado para escala, y diagramas UML. |
| [Notebook en Colab](https://colab.research.google.com/github/Joaquin1128/meli-data-governance-challenge/blob/main/notebooks/meli_enrichment_pipeline.ipynb) | Pipeline de extracción y enriquecimiento, ejecutable directo desde el repo. |

## Pipeline: extracción y enriquecimiento

Corre en Google Colab. Requiere tres secrets configurados antes de la primera
corrida (panel de secrets de Colab, ícono de llave): `GEMINI_API_KEY`,
`MELI_CLIENT_ID`, `MELI_CLIENT_SECRET`. Un cuarto secret, `MELI_REFRESH_TOKEN`, se
obtiene la primera vez que se corre el notebook (sección 3a) y hay que
actualizarlo después de cada corrida, porque MercadoLibre lo rota en cada uso.

Al terminar, el notebook deja dos artefactos:

- `meli_products.db`: SQLite con el detalle de cada producto y su
  `enrichment_status` (`pending` / `enriched` / `skipped` / `error`).
- `enriched_products_export.json`: snapshot desnormalizado del mismo contenido.

La API lee directamente de `meli_products.db`. Después de correr el notebook,
descargá ese archivo desde el panel de archivos de Colab (ícono de carpeta a la
izquierda) y copialo a la raíz de este repo antes de levantar la API, ya sea
local o con Docker Compose.

Este paso manual (descargar el archivo de Colab y copiarlo a la raíz del repo)
es solo por las condiciones de este challenge. En un entorno de producción real
la base no sería un archivo SQLite local: sería una base de datos gestionada en
la nube (por ejemplo Postgres), para que el pipeline escriba y la API lea
directamente sobre la misma fuente, sin depender de mover un archivo entre
procesos (ver [`docs/informe.md`](docs/informe.md), sección 2.1).

## API: instalación y ejecución

Requiere Python 3.11+.

### Local

```bash
python -m venv .venv
source .venv/bin/activate

pip install -e .
pip install -r requirements-api.txt

# meli_products.db generado por el notebook, o el propio (ver más abajo)
export MELI_API_DB_PATH=meli_products.db

uvicorn meli_api.adapters.inbound.http.app:app --reload
```

La API queda en `http://localhost:8000`. Documentación interactiva en `/docs`,
especificación OpenAPI en `/openapi.json`.

Sin un Redis disponible, correr con el cache deshabilitado en vez de apuntar a un
Redis inexistente (el circuit breaker igual lo tolera, pero así se evita el ruido
de los primeros fallos mientras abre):

```bash
export MELI_API_CACHE_BACKEND=none
```

### Con Docker Compose

Levanta la API y Redis juntos. Requiere tener `meli_products.db` en la raíz del
repo (el `docker-compose.yml` lo monta como volumen de solo lectura):

```bash
docker compose up --build
```

### Tests

```bash
pip install -r requirements-dev.txt
pytest
```

La suite está separada en `tests/unit` (dominio y casos de uso, sin I/O),
`tests/integration` (SQLite y Redis reales/temporales) y `tests/e2e` (API completa
vía `TestClient`).

## Variables de entorno

Todas con prefijo `MELI_API_`, leídas también desde un archivo `.env` en la raíz.

| Variable | Default | Descripción |
|---|---|---|
| `MELI_API_DB_PATH` | `meli_products.db` | Ruta a la SQLite generada por el pipeline. |
| `MELI_API_CACHE_BACKEND` | `redis` | `redis` (cache-aside real) o `none` (`NullCache`, cache deshabilitado a propósito). |
| `MELI_API_REDIS_URL` | `redis://127.0.0.1:6379/0` | URL de conexión a Redis. |
| `MELI_API_CACHE_TTL_DETAIL_SECONDS` | `300` | TTL de cache para `GET /products/{item_id}`. |
| `MELI_API_CACHE_TTL_LIST_SECONDS` | `60` | TTL de cache para `GET /products`. |
| `MELI_API_REDIS_BREAKER_FAIL_MAX` | `5` | Fallos consecutivos antes de abrir el circuit breaker de Redis. |
| `MELI_API_REDIS_BREAKER_RESET_TIMEOUT_SECONDS` | `30` | Cooldown antes de reintentar Redis (half-open). |
| `MELI_API_RATE_LIMIT_PER_MINUTE` | `60` | Límite de requests por IP en `/products` y `/products/{item_id}`. |

## Endpoints

| Método | Path | Descripción |
|---|---|---|
| `GET` | `/products` | Listado paginado. Filtros: `status` (`pending`/`enriched`/`skipped`/`error`), `q` (texto libre en el nombre). Params: `limit` (1-100), `offset`. |
| `GET` | `/products/{item_id}` | Detalle de un producto: nombre, descripción (enriquecida o fallback a la original), `enrichment_status`, imagen, precio, moneda, rating, especificaciones, permalink. |
| `GET` | `/health` | Estado de SQLite y Redis por separado (`ok` / `degraded` / `down`). |
| `GET` | `/metrics` | Métricas en formato Prometheus. |

Todas las respuestas de error siguen el mismo formato:

```json
{
  "error": {
    "code": "PRODUCT_NOT_FOUND",
    "message": "Producto 'MLA000' no encontrado"
  }
}
```

Códigos usados: `PRODUCT_NOT_FOUND` (404), `INVALID_FILTER` (422),
`REPOSITORY_UNAVAILABLE` (503), `RATE_LIMIT_EXCEEDED` (429), `INTERNAL_ERROR` (500).

## Estructura del proyecto

```
notebooks/    pipeline de extracción y enriquecimiento (Colab)
src/meli_api/ API RESTful (arquitectura hexagonal: domain / application / adapters)
tests/        unit / integration / e2e
docs/         informe.md, architecture.md
```

Detalle completo de capas, puertos y decisiones de diseño en
[`docs/architecture.md`](docs/architecture.md).
