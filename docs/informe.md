# Informe — Enriquecimiento de descripciones de productos y API RESTful

> Data Governance: Desafío Técnico (Mercado Libre). Este informe complementa el
> código (`notebooks/meli_enrichment_pipeline.ipynb`, `src/meli_api/`) y la
> documentación técnica (`README.md`, `docs/architecture.md`) con el análisis que
> pide el enunciado: resultados del caso de uso, desafíos del proceso, e impacto
> de las descripciones enriquecidas en el sistema de recomendación y en su
> consumo por entidades externas.

## 1. Alcance y vínculo con el desafío de negocio

El enunciado plantea el problema en términos de tres pilares de gobierno de datos
sobre un ecosistema de más de 250 equipos y 2 millones de productos de datos:
**discoverabilidad**, **integridad de los datos** y **eficiencia operativa**. El
ejercicio concreto (enriquecer descripciones de producto y exponerlas vía una API)
es una instancia acotada de ese problema general, y las decisiones de diseño de
este proyecto responden explícitamente a esos tres pilares:

| Pilar | Cómo lo aborda esta solución |
|---|---|
| **Discoverabilidad** | La API expone un contrato único y documentado (`GET /products`, `GET /products/{id}`, OpenAPI en `/docs`) para que cualquier equipo -- el sistema de recomendación, un comparador de ítems, u otro consumidor no previsto hoy -- encuentre y entienda los datos enriquecidos sin tener que conocer el pipeline interno ni el esquema de SQLite. `enrichment_status` hace visible, por cada producto, si el dato que se está consumiendo es enriquecido o no, en vez de esconder esa distinción. |
| **Integridad de los datos** | El prompt de enriquecimiento prohíbe explícitamente inventar atributos no presentes en las especificaciones u la descripción original (`notebooks/meli_enrichment_pipeline.ipynb`, sección 7); la API nunca oculta ni reemplaza silenciosamente un dato ausente (fallback explícito a `original_description`, nunca un campo vacío sin explicación); y el manejo de errores es descriptivo en vez de fallar en silencio (sección 3 de `docs/architecture.md`). |
| **Eficiencia operativa** | El pipeline selecciona qué enriquecer con una regla simple y auditable (`needs_enrichment`: solo descripciones ausentes o cortas), para no gastar cuota de Gemini en ítems que ya están bien descriptos. La API cachea (Redis, cache-aside) las lecturas más frecuentes, y su arquitectura hexagonal permite escalar o reemplazar componentes (DB, cache, incluso el proveedor de LLM del pipeline) sin reescribir el sistema completo. |

Esta tabla es la respuesta directa a "cómo se aborda el desafío de negocio" que el
enunciado dice que se evalúa por encima del código en sí.

## 2. Proceso: decisiones y desafíos enfrentados

### 2.1 Pipeline de extracción y enriquecimiento (offline)

- **Autenticación de un solo uso.** El `refresh_token` de OAuth2 de MercadoLibre se
  invalida en cada uso y el servidor entrega uno nuevo (`notebooks/...`, sección 3b).
  Esto obliga a persistir el token nuevo después de cada corrida -- un detalle fácil
  de pasar por alto que, si no se maneja, deja el pipeline inutilizable hasta repetir
  el login manual por navegador.
- **Persistencia del token y de la base entre corridas: se evaluó automatizarla y se
  descartó para este entregable.** Se consideró guardar el `refresh_token` y
  `meli_products.db` en Google Drive (montado desde el propio notebook) para evitar
  el paso manual de copiar el token nuevo a los secrets de Colab y de descargar la
  base para usarla con la API. Se descartó porque asume un entorno específico de
  quien corre el notebook (una cuenta de Drive propia, opcionalmente Drive Desktop
  sincronizado localmente para que la API la lea sin descarga manual) que un script
  pensado para una evaluación acotada no debería requerir -- cambiaría una fricción
  conocida (copiar el token, descargar un archivo chico, ambos ya documentados paso
  a paso en el README) por una dependencia nueva que podría no aplicar en el entorno
  de quien lo evalúa. Queda como mejora identificada para un uso personal recurrente
  del pipeline, no como algo que le falte al entregable. En un entorno de producción
  real, en cambio, ninguna de las dos cosas se resolvería con Drive: el
  `refresh_token` iría a un secret manager (no a un archivo), y la base pasaría de
  SQLite local a una base de datos en la nube (por ejemplo Postgres gestionado),
  para que el pipeline escriba y la API lea sin necesidad de mover un archivo entre
  procesos -- es la extensión natural de la arquitectura de solo lectura ya descrita
  en 2.2, cambiando el adapter de persistencia sin tocar el resto del sistema.
- **Selección de qué enriquecer.** En vez de enriquecer todo el catálogo extraído
  (lo que gastaría cuota de Gemini innecesariamente), se enriquece solo lo que tiene
  descripción ausente o por debajo de un umbral de longitud (`MIN_DESCRIPTION_LENGTH`).
  Esta es una decisión de eficiencia operativa tomada a nivel de diseño del pipeline,
  no un detalle de implementación menor.
- **Restricciones éticas en el prompt.** El enunciado pide explícitamente "evitar
  adornar o cambiar la sustancia de la información original sin razón justificada".
  El prompt (`DescriptionEnricher._build_prompt`) traduce eso en restricciones
  concretas y verificables: no inventar atributos fuera de las especificaciones,
  tono neutral-profesional, límite duro de 400 caracteres, sin markdown. Esto es lo
  que hace que la integridad de los datos (pilar 2) sea algo exigible, no una
  declaración de intención.
- **Resiliencia ante servicios externos.** Tanto el cliente de MELI como el de
  Gemini reintentan con backoff exponencial ante `429`/`5xx` y errores transitorios
  respectivamente (secciones 5 y 7 del notebook). Esto vive enteramente en el
  pipeline offline, no en la API (ver 2.2). El backoff está implementado a mano
  (`_exponential_backoff_seconds`, ~10 líneas) en vez de agregar `tenacity` como
  dependencia: para dos únicos puntos de reintento con la misma política simple
  (exponencial, sin jitter, tope fijo de intentos), una librería dedicada no
  aporta sobre el código propio y suma una dependencia más al notebook. `tenacity`
  queda como la opción a adoptar si la política de reintentos creciera en
  complejidad (jitter, reintentos condicionales por tipo de error, etc.), no como
  un requisito de este alcance.
- **Elección del modelo de Gemini (dos idas y vueltas, documentadas porque las
  dos dejaron una lección concreta).**
  1. Se arrancó con `gemini-flash-lite-latest` para economizar cuota (decisión de
     eficiencia operativa, pilar 3), pero no seguía el límite de longitud del
     prompt de forma consistente (ver 3.3: 33-52% de las descripciones excedían
     los 400 caracteres según la corrida).
  2. Se probó reforzar esto con un reintento a nivel de código cuando la
     descripción excedía el límite -- pero eso triplicaba las llamadas a Gemini
     por producto en los casos afectados, agotando la cuota real más rápido, no
     más lento. Se revirtió (una descripción algo larga es preferible a gastar
     cuota reintentando sin garantía de éxito), y se probó `gemini-flash-latest`
     (la variante estándar, no lite) bajo la hipótesis de que seguiría
     instrucciones de formato con más consistencia.
  3. `gemini-flash-latest` devolvió `503 UNAVAILABLE` ("This model is currently
     experiencing high demand") de forma sostenida durante una corrida real,
     agotando los 3 reintentos con backoff exponencial (2s, 4s, 8s) para varios
     productos consecutivos y dejándolos sin enriquecer (`status = error`). Es un
     problema de disponibilidad del lado de Google, no del código del pipeline --
     pero para los fines prácticos de completar el challenge, la disponibilidad
     pesa más que una consistencia de formato marginalmente mejor. Se volvió a
     `gemini-flash-lite-latest` (variante más chica, aparentemente con menor
     contención en el momento de las pruebas), aceptando el problema conocido de
     longitud/consistencia de estilo (documentado en 3.3) como trade-off
     consciente frente a directamente no poder completar la corrida.

### 2.2 Decisión de diseño: la API es de solo lectura

La decisión más importante tomada al arrancar la implementación de la API fue que
esta **no llama a MELI ni a Gemini en tiempo real**: solo lee lo que el pipeline
offline ya persistió en SQLite. Esto simplifica radicalmente la superficie de
fallas de la API (sus únicas dependencias son SQLite y, opcionalmente, Redis) y
separa con claridad dos responsabilidades que el enunciado tiende a mezclar en un
solo "proceso": generar el dato enriquecido (pipeline, con sus propios reintentos y
límites de tasa) y servirlo de forma confiable y rápida a consumidores (API, con
cache y circuit breakers propios). El detalle completo de esta arquitectura está en
`docs/architecture.md`.

### 2.3 Desafíos técnicos encontrados al implementar la API

Tres problemas concretos, no anticipados en el diseño inicial, aparecieron recién al
probar la API con un servidor `uvicorn` real (no solo con `TestClient`, que no
ejercita la red):

1. **`redis-py` reintenta por su cuenta.** El cliente trae por default un retry de
   hasta 10 intentos con backoff exponencial ante errores de conexión/timeout,
   duplicando silenciosamente la política de reintentos que ya se había decidido
   delegar enteramente al circuit breaker propio. Sin desactivarlo explícitamente,
   cada llamada a un Redis caído tardaba varios segundos en vez de fallar rápido.
2. **Resolución dual de `localhost`.** Con Redis caído, resolver `localhost` prueba
   primero la dirección IPv6 (`::1`) y después la IPv4 (`127.0.0.1`), duplicando el
   timeout de conexión configurado en cada intento fallido. Se resolvió fijando el
   host por default a la IP literal `127.0.0.1`.
3. **Logging duplicado de uvicorn.** El servidor trae su propio access log en texto
   plano, independiente del logging estructurado (JSON) que ya provee este proyecto
   con más contexto (`request_id`, latencia, etc.). Se desactivó explícitamente para
   no mezclar dos formatos de log.

Los dos primeros (retry duplicado de `redis-py` y resolución dual de `localhost`)
están documentados en detalle, con la causa raíz verificada, en
`docs/architecture.md` (sección 8bis); el tercero (logging duplicado de uvicorn)
en la sección 5 del mismo documento. Se dejan como ejemplo concreto de por qué
"probarlo con un servidor real" es parte del proceso y no un paso opcional: ninguno
de estos tres problemas se hubiera detectado con tests puramente unitarios o con
`TestClient`, que no abre sockets reales.

### 2.4 Otras limitaciones conocidas del prototipo

- El rate limiter y el circuit breaker de Redis son **por proceso** (en memoria):
  con más de una instancia de la API corriendo, cada una lleva su propia cuenta. Es
  una limitación aceptada explícitamente para el prototipo y documentada en
  `docs/architecture.md` (sección 6) junto con cómo se resolvería a escala real
  (gateway central, storage compartido).
- La API no tiene autenticación en este prototipo (decisión tomada explícitamente,
  ver `docs/architecture.md`, sección 6), documentada como pendiente para un
  entorno real.

## 3. Resultados del caso de uso

Tres corridas reales de `notebooks/meli_enrichment_pipeline.ipynb` contra la API de
MercadoLibre (`SEARCH_QUERY = "notebook gamer"`, `MELI_SITE_ID = "MLA"`,
`MAX_ITEMS = 50`) y Gemini (`gemini-flash-lite-latest`), con los resultados
persistidos en `meli_products.db` y analizados directamente contra esa base (no
sobre una muestra ni sobre el JSON exportado):

- **Corrida 1**: con el prompt original (sin instrucción de idioma). Reveló los
  hallazgos que se describen abajo.
- **Corrida 2**: con el prompt corregido (instrucción explícita de salida en
  español, agregada a partir del hallazgo de la Corrida 1). Sobre el mismo
  catálogo (mismos 50 `item_id`, el listado de MELI para esta búsqueda no cambió
  entre corridas), sirve como verificación directa de que el fix funcionó.
- **Corrida 3**: con las dos instrucciones agregadas después de la Corrida 2 --
  variar la apertura de la descripción, y preferir el nombre del producto sobre
  una especificación estructurada en conflicto (ver 3.4, puntos 3 y 4) -- ya
  aplicadas. Verifica el efecto de esos dos fixes sobre el mismo catálogo.

Esta sección reporta las tres, porque el contraste entre corridas es en sí mismo el
resultado más útil del análisis: muestra un hallazgo real, la corrección aplicada,
y la verificación de que la corrección tuvo el efecto esperado -- no solo el
estado final.

### 3.1 Métricas generales (las tres corridas)

| Métrica | Corrida 1 | Corrida 2 | Corrida 3 |
|---|---|---|---|
| Productos extraídos | 50 | 50 | 50 |
| Enriquecidos (`enriched`) | 21 (42%) | 21 (42%) | 21 (42%) |
| Omitidos (`skipped`) | 29 (58%) | 29 (58%) | 29 (58%) |
| Con error (`error`) | 0 | 0 | 0 |
| Productos con `price` poblado | 0 de 50 | 0 de 50 | 0 de 50 |
| Productos con `rating` poblado | 0 de 50 | 0 de 50 | 0 de 50 |

Que la selección (`enriched`/`skipped`/`error`) sea idéntica entre las tres
corridas es esperable: los cambios de prompt no afectan a `needs_enrichment` (que
corre antes, sobre datos de MELI, no sobre la salida de Gemini). Dos observaciones
que valen para las tres corridas:

- El umbral de selección (`needs_enrichment`, `MIN_DESCRIPTION_LENGTH = 60`)
  funcionó sin excepciones sobre los 50 productos: los 21 enriquecidos tenían
  `original_description` vacía (longitud 0, no simplemente corta) y los 29
  omitidos tenían descripciones de 322 caracteres o más -- no hay ningún caso
  límite ambiguo en esta búsqueda. Esto sugiere que, para "notebook gamer" en MLA,
  la población de productos está polarizada entre "sin descripción" y "con
  descripción larga ya cargada", más que distribuida en un rango intermedio.
- **`price` y `rating` quedaron en `None` para el 100% de los productos, en las
  tres corridas.** `rating` es un campo esperado en `None` (el endpoint
  `/products/{id}` de MercadoLibre no lo expone, ya señalado como limitación
  conocida en el código: `notebooks/...`, sección 4). `price` depende de que
  exista un `buy_box_winner` en la respuesta de MELI -- que ninguno de los 50
  productos lo tuviera, de forma consistente entre corridas, sugiere que la
  búsqueda cae sobre fichas de catálogo sin oferta activa asociada, y sería el
  primer punto a investigar si se quisiera usar `price` como señal real en el
  sistema de recomendación.

### 3.2 Ejemplos concretos de antes/después

**Caso 1 -- enriquecimiento sin descripción original (el caso típico: 21/21).**

- Producto: `MLA23985848` -- "Notebook Gamer Asus 15,6'' I5 16gb 512gb Win11"
- `original_description`: `""` (vacía)
- `enriched_description` (Corrida 2, prompt corregido): *"Potencia tu rendimiento
  con la notebook gamer Asus Zephyrus de 15,6 pulgadas, equipada con un procesador
  Intel Core i5 y 16 GB de RAM DDR5. Cuenta con una unidad SSD de 512 GB y
  resolución de pantalla de 1920x1080 píxeles para una experiencia fluida. Además,
  ofrece conectividad Wi-Fi, Bluetooth, puertos USB y HDMI, teclado retroiluminado
  y Windows 11 preinstalado."* (366 caracteres, 3 oraciones, español)

Este es el caso que justifica el enriquecimiento: un producto que llegaría a
cualquier sistema de recomendación con cero señal textual (`description` vacío)
ahora tiene una descripción completa, correcta contra las especificaciones
estructuradas del producto, de longitud/tono consistente, y en el idioma del
resto del catálogo.

**Caso 2 -- reconciliación entre el título del producto y una especificación que
parece errónea en el catálogo de origen (se mantiene igual en las tres corridas).**

- Producto: `MLA23140641` -- "Notebook Gamer Lenovo Legion I7 8750h 1tb 8gb 15.6
  Gtx1050"
- Especificación estructurada extraída de MELI: `"Capacidad del disco rígido":
  "1 GB"` -- un valor casi con certeza incorrecto en el catálogo de origen (una
  notebook gamer con disco rígido de 1 GB no es un producto real; el título del
  aviso dice "1tb").
- `enriched_description` (Corrida 2 y 3, idéntico en ambas): *"...acompañada por
  8 GB de RAM DDR4 y un disco rígido de **1 TB**..."*

El modelo generó la descripción usando `1 TB` (lo que dice el título del aviso, y
lo que tiene sentido para el producto real) en vez de `1 GB` (lo que dice,
erróneamente, el atributo estructurado) -- y lo hizo igual en las tres corridas.
En las Corridas 1 y 2 esto ocurrió **sin que el prompt lo indicara**: el prompt le
pedía explícitamente "no inventar atributos fuera de las especificaciones o la
descripción original", pero no aclaraba qué hacer si el *nombre* del producto
contradice una especificación estructurada, y el modelo resolvió esa ambigüedad
razonablemente por su cuenta. Para la Corrida 3 se agregó al prompt una
instrucción explícita para este caso (preferir el nombre del producto cuando una
especificación es claramente implausible, ver 3.4 punto 3) -- y el resultado no
cambió respecto a las corridas anteriores, lo cual es la verificación esperada:
formalizar en el prompt un comportamiento que el modelo ya tenía no debería
alterar el resultado, solo dejar de depender de que seguiera resolviéndolo bien
por inferencia. Esto es relevante para el pilar de **integridad de los datos**
del desafío por dos motivos: primero, expone que el catálogo de origen de MELI
puede tener errores de carga en atributos estructurados que un proceso automático
no detectaría si solo mirara esos atributos; segundo, muestra que dejar esta
regla implícita en las dos primeras corridas era un riesgo real aunque no se
haya materializado -- la instrucción explícita de la Corrida 3 cierra ese
comportamiento no especificado (ver 3.3 y 3.4, punto 3).

**Caso 3 -- verificación del fix de idioma: mismo producto, dos corridas.**

- Producto: `MLA23241253` -- "Notebook Gamer Hp Omen / I7 / 16ram/ 512ssd/ Rtx2070
  / 144hz"
- Corrida 1 (prompt sin instrucción de idioma): *"Domina tus juegos y proyectos
  exigentes con la notebook HP Omen de 15.6 pulgadas, equipada con un potente
  procesador Intel Core i7 de 6 núcleos y 16 GB de RAM..."* (443 caracteres,
  español -- por casualidad, no por instrucción)
- Corrida 2 (prompt con instrucción explícita de español): *"Experimenta un
  rendimiento superior con la notebook gamer HP Omen 15-ek0007la en color negro.
  Equipada con un procesador Intel Core i7, 16 GB de RAM y almacenamiento SSD de
  512 GB con Intel Optane de 32 GB..."* (465 caracteres, español)

Y, más importante, el producto `MLA23985848` (Caso 1) que en la Corrida 1 había
salido en **inglés** ("Elevate your gaming and productivity with the Asus
Zephyrus...") en la Corrida 2 salió en **español** ("Potencia tu rendimiento
con..."). El enunciado pide que "los prompts sean en inglés" -- una instrucción
sobre el *prompt* (las instrucciones que recibe el modelo), no sobre el idioma en
el que debe responder. El prompt original nunca especificaba el idioma de la
descripción generada, y el resultado en la Corrida 1 fue inconsistente: 18 de 21
casos (86%) en inglés (siguiendo, por inercia, el idioma de las instrucciones) y 3
de 21 (14%) en español. Para el mercado real de esta corrida (MLA, Argentina, con
`name` y `specifications` ya en español), lo correcto de cara al negocio es que
**toda** la descripción esté en español -- consistente con el resto de la ficha
del producto y con el idioma del consumidor final. Se agregó al prompt la
instrucción explícita ("Output language: Spanish [...] regardless of the fact
these instructions are written in English"), manteniendo las instrucciones en
inglés como pide el enunciado. **Resultado verificado en la Corrida 2: 21 de 21
(100%) en español, sin excepciones** (ver 3.3).

**Caso 4 -- contraste con un producto omitido (`skipped`).**

- Producto: `MLA34198936` -- "Notebook Gamer Hp Victus 16-d0503la Color Azul"
- `original_description` (sin tocar, 1046 caracteres): ya trae secciones con
  subtítulos ("Pantalla con gran impacto visual", "Eficiencia a tu alcance",
  "Potente disco sólido"...) redactadas por el vendedor o por MELI, con buena
  cobertura de las especificaciones del producto.

Este caso confirma que la regla de selección (`needs_enrichment`) está evitando
correctamente gastar cuota de Gemini en un producto que ya tiene una descripción
extensa y razonable -- es exactamente el comportamiento de eficiencia operativa
que buscaba el diseño del pipeline (sección 2.1). Con el prompt corregido (Corridas
2 y 3), esta descripción "buena" (español, con subtítulos) y las descripciones
enriquecidas (español, en prosa corrida sin subtítulos) ya comparten idioma; la
diferencia de estilo restante (subtítulos vs. prosa corrida) es un problema
distinto y menor, esperable porque un producto `skipped` conserva el formato que
le dio originalmente el vendedor o MELI, sin pasar por el enriquecimiento.

### 3.3 Observaciones de calidad y consistencia (evolución sobre las tres corridas)

| Observación | Corrida 1 (prompt original) | Corrida 2 (+ fix de idioma) | Corrida 3 (+ variar apertura, + preferir `name`) |
|---|---|---|---|
| Longitud de `enriched_description` | 347-463 caracteres, promedio 404 | 312-476 caracteres, promedio 383 | 361-483 caracteres, promedio 409 |
| Excede el límite de 400 caracteres del prompt | 11 de 21 (52%) | 7 de 21 (33%) | **12 de 21 (57%)** -- empeoró, sin cambio de prompt que lo explique |
| Estructura de 2-3 oraciones | 21 de 21 (100%) | 21 de 21 (100%) | 21 de 21 (100%; 19 con 3, 2 con 2) |
| Uso de markdown/bullets (prohibido) | 0 de 21 | 0 de 21 | 0 de 21 |
| Idioma de salida | 18/21 inglés, 3/21 español (inconsistente) | 21 de 21 (100%) en español | **21 de 21 (100%) en español** -- fix se sostiene |
| Repetición de apertura | 11/21 (52%) arrancan con "Elevate" | 11/21 (52%) arrancan con "Notebook" | **máx. 8/21 (38%) con "Equipada"** -- mejoró, no se eliminó |
| Uso de datos del título sobre una especificación estructurada | 2 de 21 casos | El mismo caso (`MLA23140641`, Caso 2) se repite igual | El mismo caso se repite una tercera vez, ahora con instrucción explícita en el prompt |

Lectura de esta tabla, más allá de los números:

- **El fix de idioma funcionó exactamente como se esperaba y se sostiene en una
  tercera corrida: 100% de consistencia en las dos últimas corridas.** Esto es lo
  que respondía la pregunta original de este análisis ("¿deberían ser en español
  las descripciones?") -- sí, y siguen siéndolo, de forma medible y estable.
- **El límite de longitud del prompt sigue sin cumplirse de forma confiable, y la
  Corrida 3 muestra que la variabilidad va en ambas direcciones, no solo hacia la
  mejora.** Bajó de 52% a 33% entre Corrida 1 y 2, pero subió a 57% en la Corrida
  3 -- sin que ningún cambio de prompt entre 2 y 3 tocara la longitud. Esto
  refuerza (no contradice) la conclusión ya documentada: el modelo
  `gemini-flash-lite-latest` no respeta el límite de forma confiable corrida a
  corrida, y confiar en el prompt solo no alcanza. Un sistema que dependa de ese
  límite (ancho fijo en UI, costo de tokenización en un pipeline de embeddings)
  necesita una validación posterior explícita (truncar o volver a pedir la
  generación), no asumir cumplimiento porque está en las instrucciones.
- **La convergencia estilística mejoró con la instrucción explícita de variar la
  apertura, pero no desapareció.** De un único término dominante en 52% de los
  casos (Corridas 1 y 2) bajó a un máximo de 38% ("Equipada") en la Corrida 3, con
  una segunda agrupación cercana ("Equipado", misma raíz). Es una mejora real y
  medible, no ruido -- pero confirma que instruir "variar la apertura" atenúa sin
  eliminar la tendencia del modelo a converger en frases similares para productos
  de la misma categoría (riesgo de "uniformidad excesiva" anticipado en 4.3).
- **La reconciliación entre `name` y una especificación estructurada errónea
  (Caso 2) es reproducible en las tres corridas**, incluida la Corrida 3 donde ya
  hay una instrucción explícita en el prompt para este caso. El resultado no
  cambió respecto a cuando el comportamiento era implícito -- lo cual es la
  verificación esperada: la instrucción explícita no debía cambiar un resultado
  que el modelo ya acertaba, solo dejar de depender de que lo siguiera acertando
  sin que estuviera especificado (ver 3.4, punto 3).

### 3.4 Qué se haría distinto con este resultado en mano

Ninguno de estos hallazgos requiere cambiar la arquitectura de la API ni del
pipeline -- son ajustes acotados al prompt y a la validación posterior a la
llamada a Gemini, coherentes con la separación de responsabilidades ya descrita en
la sección 2.2:

1. **Probado y revertido dos veces (ver 2.1 para el detalle completo).** Primero
   se implementó un reintento a nivel de código que volvía a pedir la generación
   si `len(text) > 400`; se revirtió porque triplicaba las llamadas a Gemini y
   agotaba la cuota más rápido, no más lento. Después se probó `gemini-flash-latest`
   (variante estándar, sin ese reintento) esperando mejor cumplimiento del límite;
   se revirtió también porque devolvió `503 UNAVAILABLE` de forma sostenida
   ("high demand") y dejó productos sin enriquecer. Se volvió a
   `gemini-flash-lite-latest`, aceptando el problema de longitud (documentado en
   3.3) como trade-off consciente frente a la disponibilidad: hoy se acepta la
   longitud que devuelva el modelo en el primer intento exitoso, sin reintentar
   por eso. La Corrida 3 confirma que el problema no es monótono: el porcentaje de
   excesos subió a 57% (peor que las Corridas 1 y 2, ver 3.3) sin ningún cambio de
   prompt relacionado con longitud entre esas corridas -- es variabilidad propia
   del modelo, no una regresión introducida. Sigue siendo la recomendación de más
   largo plazo (para un entorno con cuota/infraestructura propia, no la de un
   challenge): validar y truncar de forma segura si excede el límite, sin que esa
   validación dispare llamadas adicionales al modelo.
2. **Aplicado y verificado con datos.** Se agregó al prompt una instrucción
   explícita de idioma ("Output language: Spanish [...] regardless of the fact
   these instructions are written in English"). La Corrida 1 (86% inglés / 14%
   español, inconsistente) y la Corrida 2 (100% español) sobre el mismo catálogo
   confirman que el fix elimina la inconsistencia de idioma por completo.
3. **Aplicado y verificado con datos.** Se aclaró en el prompt que, ante un
   conflicto entre el nombre del producto y una especificación estructurada
   claramente implausible, se prefiere el nombre (la especificación puede tener
   errores de carga del catálogo de origen). El caso `MLA23140641` -- que ya se
   había resuelto igual en las Corridas 1 y 2 sin esta instrucción -- dio el mismo
   resultado en la Corrida 3 con la instrucción explícita: confirma que formalizar
   el comportamiento no lo alteró, y elimina la dependencia de que el modelo lo
   siguiera infiriendo bien por su cuenta.
4. **Aplicado y parcialmente verificado con datos -- mejora real, no
   resuelto del todo.** Se agregó al prompt la instrucción de variar la apertura
   de la descripción entre productos. En la Corrida 3, la repetición máxima de una
   misma palabra de apertura bajó de 52% (Corridas 1 y 2) a 38% ("Equipada"). Es
   una mejora medible, pero no elimina la convergencia: sigue siendo el hallazgo
   abierto de más largo plazo si se quisiera bajar más ese número (por ejemplo,
   pasando una lista de aperturas ya usadas en la corrida como parte del prompt
   de cada llamada siguiente, en vez de solo pedir "variá" de forma genérica).

## 4. Impacto de las descripciones enriquecidas en el sistema de recomendación

### 4.1 Qué problema resuelve el enriquecimiento

Un sistema de recomendación o de comparación de ítems que opera sobre texto libre
(descripciones) típicamente depende de una de dos vías: (a) generar embeddings
semánticos de la descripción para medir similitud/relevancia entre ítems, o (b)
extraer señales estructuradas (entidades, atributos) a partir del texto para
matching y filtrado. Ambas vías se degradan cuando la descripción de origen es:

- **Ausente o extremadamente corta**: el vendedor no cargó descripción, o cargó una
  línea genérica. Un embedding sobre texto vacío o casi vacío no aporta señal
  distintiva -- el ítem queda mal representado en el espacio semántico, lo que en la
  práctica se traduce en recomendaciones pobres o en el "cold-start problem" a nivel
  de ítem (no de usuario): el sistema no tiene con qué compararlo contra el resto
  del catálogo hasta que acumule suficiente interacción de usuarios.
- **Inconsistente en tono o estructura**: descripciones que mezclan mayúsculas,
  jerga de venta, información de envío, o formato de lista sin estructura, agregan
  ruido al embedding y dificultan la extracción de atributos.

El enriquecimiento, tal como está diseñado en este proyecto (prompt con tono fijo,
longitud acotada, prohibición de inventar atributos), ataca directamente el primer
problema (densidad semántica mínima garantizada) sin introducir el riesgo más obvio
de "mejorar" texto con un LLM, que es la alucinación de atributos no presentes: si
el modelo inventa que un producto tiene una característica que no tiene, cualquier
sistema de recomendación que confíe en esa descripción va a recomendar el ítem para
consultas o comparaciones donde no corresponde, lo cual es peor que no enriquecerlo.
Por eso la restricción de no inventar atributos (sección 2.1) no es un detalle
ético abstracto: es una precondición para que el enriquecimiento mejore, en vez de
degradar, la calidad de las recomendaciones.

### 4.2 Mecanismos concretos de mejora

- **Cobertura semántica mínima garantizada.** Todo ítem que entra a `enriched`
  cuenta con al menos una descripción de longitud y estructura consistente, lo que
  reduce la varianza de calidad de input para el modelo de embeddings/recomendación
  y mitiga el cold-start de ítem mencionado arriba.
- **Comparabilidad entre ítems similares.** Un tono y formato homogéneos entre
  productos de una misma categoría hacen que la distancia semántica entre
  descripciones refleje mejor diferencias reales de producto, y no diferencias de
  estilo de redacción del vendedor original.
- **Trazabilidad de la fuente del dato.** El campo `enrichment_status` (expuesto en
  la API) permite que el sistema de recomendación pondere de forma distinta una
  descripción enriquecida (`enriched`) de una original sin tocar (`skipped`,
  `pending`) o de un fallback por falla (`error`) -- por ejemplo, dándole menor peso
  o marcándola para revisión, en vez de tratarlas como equivalentes.

### 4.3 Riesgos y cómo medir el impacto real

El enriquecimiento no es garantía de mejora automática; conviene medirlo, no
asumirlo:

- **Riesgo de alucinación residual.** Ninguna restricción de prompt es 100%
  efectiva; conviene un muestreo periódico (QA humano) de descripciones enriquecidas
  contra las especificaciones de origen, sobre todo antes de escalar el volumen de
  ítems procesados.
- **Riesgo de uniformidad excesiva.** Un mismo modelo con el mismo prompt sobre
  miles de productos similares puede converger a frases muy parecidas entre sí, lo
  que reduciría en vez de aumentar la separabilidad semántica entre ítems de una
  misma subcategoría. Esto es medible comparando la dispersión de embeddings antes y
  después del enriquecimiento sobre una muestra de la misma categoría.
- **Métricas propuestas para validar el impacto en producción** (no implementadas en
  este prototipo, pero es lo que se instrumentaría en un entorno real):
  - Comparación de embeddings: distancia intra-categoría e inter-categoría antes y
    después del enriquecimiento, para verificar que el enriquecimiento aumenta la
    separabilidad entre productos distintos sin colapsar productos similares entre sí.
  - Métricas de negocio del sistema de recomendación aguas abajo (CTR, tasa de
    conversión de ítems recomendados) comparando cohortes con y sin descripción
    enriquecida, vía A/B test.
  - Tasa de reclamos o discrepancias reportadas entre la descripción mostrada y el
    producto real, como proxy de integridad del dato (pilar 2 del desafío).

## 5. Consumo de la API por entidades externas

### 5.1 Contrato y descubribilidad

La API expone un contrato REST/JSON versionable, con especificación OpenAPI
autogenerada por FastAPI (`/openapi.json`, documentación interactiva en `/docs`).
Cualquier equipo externo -- el sistema de recomendación, un buscador, un dashboard
de calidad de catálogo -- puede generar un cliente tipado a partir de ese schema sin
coordinación manual con el equipo dueño de la API, que es exactamente el problema de
discoverabilidad que plantea el enunciado a nivel de toda la organización, resuelto
acá a nivel de este servicio puntual.

### 5.2 Qué falta para un consumo externo real (hoy documentado, no implementado)

- **Autenticación y autorización.** El prototipo queda deliberadamente abierto (ver
  `docs/architecture.md`, sección 6); un entorno real necesitaría API key u OAuth2
  `client_credentials` gestionado centralmente, con cuotas por consumidor.
- **Versionado del contrato.** Se decidió no versionar el path (`/products`, no
  `/v1/products`) para el prototipo; un consumidor externo real necesita garantías
  de que un cambio de contrato no rompe su integración sin aviso -- esto se resolvería
  versionando el path o negociando por header, con una política de deprecación
  explícita.
- **Cuotas diferenciadas por consumidor.** El rate limiting actual es un límite
  plano por IP; un ecosistema con 250+ equipos consumiendo la misma API necesita
  cuotas por API-key/cliente, típicamente en el API Gateway central, no en cada
  servicio.
- **Modo de consumo: pull vs. batch.** La API actual sirve bien un patrón de
  consulta puntual (un ítem, o una página filtrada) para un sistema que resuelve
  recomendaciones en el momento. Un consumidor que necesite el catálogo enriquecido
  completo para (re)entrenar embeddings offline se beneficiaría de un endpoint de
  export masivo (o de leer directamente un snapshot/data lake), no de paginar
  `GET /products` con `limit=100` miles de veces -- esto es una extensión natural, no
  implementada, que valdría la pena evaluar según el consumidor real.

### 5.3 Gobernanza del dato consumido externamente

Un consumidor externo de esta API no solo necesita el dato: necesita poder confiar
en él y entender su procedencia, que es el corazón del pilar de integridad del
desafío. Dos decisiones ya tomadas en este proyecto apuntan directamente a eso:

- `enrichment_status` viaja en cada respuesta, así que ningún consumidor externo
  puede confundir accidentalmente una descripción generada por Gemini con la
  original del vendedor.
- Los códigos de error son explícitos y diferenciados (`PRODUCT_NOT_FOUND`,
  `REPOSITORY_UNAVAILABLE`, `RATE_LIMIT_EXCEEDED`, etc., ver `README.md`), en vez de
  un genérico "error" -- un requisito que el propio enunciado pide explícitamente
  ("códigos de error descriptivos... para facilitar la identificación y resolución
  de problemas por parte de los usuarios que la consumen").

## 6. Especificación de la API

La especificación completa de endpoints, parámetros, variables de entorno y
formato de errores está en `README.md`; el detalle de arquitectura, puertos,
estrategia de resiliencia y observabilidad está en `docs/architecture.md`. Este
informe no las duplica para evitar que ambos documentos queden desincronizados.

## 7. Conclusiones

El ejercicio, más allá del código, exigía una postura sobre tres tensiones que
suelen aparecer en cualquier plataforma de datos a escala: qué tan lejos llevar el
enriquecimiento automático sin comprometer la integridad del dato original, cómo
mantener una API disponible cuando sus dependencias (cache, y en el caso general
también los proveedores de IA/datos) no lo están, y cómo dejar un sistema
descubrible y consumible por equipos que no participaron de su diseño. Las
decisiones documentadas en este informe y en `docs/architecture.md` -- prompt con
restricciones verificables, API de solo lectura con degradación graceful,
`enrichment_status` explícito, contrato OpenAPI autodescriptivo -- son la respuesta
concreta a esas tres tensiones dentro del alcance de este prototipo.
