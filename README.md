# Autorizaciones de Compra · Neostar

Aplicación web que automatiza el circuito de autorización de compras: se sube la
factura del proveedor, se extraen sus datos, se completa el formulario oficial
**F 8.4-01 · Autorización Genérica de Compra o Contratación (Rev. 07)** y el
autorizado elegido la firma digitalmente.

## Cómo funciona

1. **Subir factura** — se lee el PDF y se extraen proveedor, CUIT, fecha, importes,
   condiciones de pago, contacto y el detalle de ítems.
2. **Revisar y completar** — los campos leídos de la factura se muestran en verde. Con el
   CUIT, si el proveedor ya tiene solicitudes, se completan solos los datos vacíos
   (nombre, contacto, legajo, y el CBU si se elige transferencia), también en verde. El
   empleado completa lo que falta (marca, ubicación, concepto, tipo de orden, quién
   solicita) y elige **un firmante**, que recibe el aviso por mail. Los obligatorios
   tienen `*`; si falta algo, se marca en rojo debajo de cada campo y la pantalla lleva al
   primero. "Solicitado por" y la ubicación quedan recordados en el navegador.
3. **Autorizar** — el firmante elegido confirma con su PIN. Es el único que puede
   firmarla; con una firma dentro de su tope queda autorizada.
4. **PDF** — se descarga el formulario oficial completado, con quien firmó y la
   fecha/hora de cada firma. La cajera de la empresa y la ubicación recibe el aviso.

## Stack

- **Frontend**: React + Vite (JavaScript), CSS vanilla (estética Neostar, tema claro)
- **Backend**: Python 3.12 + Flask, pdfplumber (lectura), pypdf + reportlab (llenado)
- **Base de datos**: SQLite
- **Despliegue**: Docker (backend Flask servido con waitress + frontend Nginx), hora de Argentina

## Reglas del proceso

- **Un firmante por solicitud**, elegido al cargarla: solo esa persona puede firmarla
  (las cargadas antes de esta regla, sin firmante, las firma cualquier habilitado).
  Su firma la deja **autorizada**: no hay segunda firma. La misma persona no puede firmar
  dos veces.
- **CUIT del proveedor**: obligatorio y con el dígito verificador correcto
  (`server/services/cuit.py`); se guarda como `XX-XXXXXXXX-X`. Al editar una solicitud
  vieja con el CUIT mal, pide corregirlo.
- **Proveedor nuevo**: no se guarda sin el legajo impositivo (PDF).
- **PIN por persona**: cada autorizado define su PIN la primera vez que firma. Se guarda
  hasheado (PBKDF2-SHA256), nunca en claro.
- **Marca**: sólo pueden firmar los autorizados habilitados para esa marca.
  Los de **Multimarca** pueden autorizar cualquiera; la planilla de **Kia** cubre también
  Suzuki y la de **Jeep** corresponde a FCA / Chrysler.
- **Topes**: al cargar solo se puede elegir como firmante a quien cubre el monto. Si
  después deja de cubrirlo (por ejemplo, le bajaron el tope), no puede firmar: se destraba
  editando la solicitud y eligiendo otro firmante. Los directores figuran *sin límite*.
  Las viejas sin firmante siguen con la regla anterior: una firma dentro del tope alcanza;
  si lo supera, queda registrado en el PDF y hace falta una segunda de otra persona.
- **Edición**: si se edita una solicitud ya firmada, las firmas se borran y hay que
  volver a autorizar. Una autorizada no se puede modificar.
- **Devolver o rechazar**: si el firmante no está de acuerdo, en vez de firmar puede
  (con su PIN y un motivo obligatorio):
  - **devolverla para corregir**: queda *Observada*. Cuando alguien la edita vuelve a
    *Pendiente* y al firmante le llega el aviso de nuevo;
  - **rechazarla**: queda *Rechazada* para siempre. No se firma ni se edita, sigue en la
    lista como registro y solo administración la puede eliminar.

  Lo hace el firmante elegido (en las viejas sin firmante, cualquier habilitado). A quien
  la cargó no le llega mail: la app no tiene su mail. El estado, quién y el motivo se ven
  en la lista (filtro *Observadas* / *Rechazadas*) y en el detalle.

## El formulario oficial

El PDF que genera la app **no es una réplica dibujada**: se usa el formulario original
de la empresa (`server/assets/formulario_f8401_rev07.pdf`) y se escriben los valores en
las coordenadas de sus propios campos. La salida se aplana (no editable).

Detalles a tener en cuenta:

- Los 36 casilleros no están impresos en la hoja: cada campo los dibuja en su
  *appearance*. Al aplanar hay que redibujarlos (ver `services/pdf_fill.py`).
- El formulario no expone campo rellenable para *duración de orden abierta*,
  *concepto → otros* ni *condiciones → otras*: se escriben sobre la línea del original.
- El detalle tiene **6 renglones**. Si la factura trae más, la app avisa para agruparlos.
- El original tiene un único recuadro "AUTORIZADO POR". La firma del firmante elegido lo
  ocupa entero; solo se divide en dos mitades cuando hay dos firmas (solicitudes viejas).

Si sale un **Rev. 08**: reemplazar el PDF de `server/assets/` y revisar el mapa de
campos en `services/pdf_fill.py`.

## Estructura

```
client/          Frontend React + Vite
server/          Backend Flask (routes, services, models)
  assets/        Formulario oficial F 8.4-01 + logo
  services/      extractor.py (lee facturas) · pdf_fill.py (completa el formulario)
  tests/         Tests (python -m unittest discover tests, desde server/)
docs/            Documentación fuente (formulario, planillas de autorizados, factura ejemplo)
scripts/         backup.sh (backup diario de la base y los adjuntos, ver "Backups")
```

## Docker (como en producción)

`docker compose` levanta la app igual que en el servidor: el backend con **waitress**
(servidor de producción, sin modo debug ni recarga automática), con el código dentro de
la imagen y la hora de Argentina. Para desarrollar con recarga automática, ver
*Desarrollo local*.

```bash
docker compose up -d --build     # construir y levantar
docker compose logs -f backend   # ver logs del backend
docker compose down              # detener
```

- Frontend: http://localhost:8092/proceso-compra/
- Backend API: http://localhost:8092/proceso-compra/api

`docker ps` muestra el estado del backend: `(healthy)` si contesta y puede leer la base,
`(unhealthy)` tras tres fallas seguidas (se chequea cada 30 s contra `/api/health`) y
`(health: starting)` el primer medio minuto. Docker no lo reinicia por estar unhealthy;
la causa queda en `docker compose logs backend` ("health: la base no responde").

## Desplegar

En el servidor, en `/opt/portal/portal-interno/proceso-compra`:

```bash
scripts/backup.sh               # backup de la base y los adjuntos antes de tocar nada
git pull
docker compose up -d --build    # reconstruye backend y frontend y los reinicia
```

El código va **dentro de la imagen**: sin el `--build` sigue corriendo la versión
anterior. (Hasta nov-2026 alcanzaba con `git pull`, porque el backend corría en modo
desarrollo con el código montado desde la carpeta.) La base y los adjuntos no se tocan:
viven en el volumen `sqlite_data` y en `server/uploads/`.

## Backups

`scripts/backup.sh` deja todo en `/opt/portal/portal-interno/proceso-compra-backups/automaticos/`:

- **Base** (`base/`): copia en caliente con la API de backup de SQLite, así queda
  consistente aunque alguien esté firmando en ese momento. Se verifica, se comprime y se
  guardan las de los últimos **30 días**.
- **Adjuntos** (`adjuntos/`): espejo de `server/uploads/`. Solo copia los nuevos y nunca
  borra nada, así un adjunto eliminado en la app sigue estando en el backup.

Corre todos los días a las 3 de la mañana con el cron del usuario que despliega
(`crontab -e`). El servidor está en UTC, así que las 3 de Argentina son las 6:

```
0 6 * * * /opt/portal/portal-interno/proceso-compra/scripts/backup.sh >> /opt/portal/portal-interno/proceso-compra-backups/backup.log 2>&1
```

No copiar `app.db` a mano con la app andando: puede quedar a medio escribir. Para un
backup en el momento, correr el script.

**Restaurar** una copia (reemplaza la base actual: hacer antes un backup de esa):

```bash
docker compose stop backend
gunzip -c ../proceso-compra-backups/automaticos/base/app-AAAAMMDD-HHMM.db.gz > /tmp/app.db
docker cp /tmp/app.db proceso-compra-backend-1:/app/data/app.db
docker compose start backend
```

## Desarrollo local (sin Docker)

**Backend** (Python 3.12):

```bash
cd server
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
python app.py                 # http://localhost:5000
```

**Frontend** (Node 20+):

```bash
cd client
npm install
npm run dev                   # http://localhost:5173 (proxy /api -> :5000)
```

## API REST

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/facturas/extraer` | Sube el PDF y devuelve los datos leídos |
| GET | `/api/solicitudes` | Lista de a 50, la más nueva primero (`pagina`; filtros: `estado`, `q`, `empresa`, `marca`, `ubicacion`, `urgente=1`, `desde`/`hasta` aaaa-mm-dd de carga). Devuelve `solicitudes`, `total`, `pagina`, `por_pagina` |
| GET | `/api/solicitudes/excel` | La lista con los mismos filtros, toda, en Excel (.xlsx) |
| GET | `/api/proveedores/:cuit` | Datos del proveedor tomados de sus solicitudes anteriores (para el alta) |
| POST | `/api/solicitudes` | Crea |
| GET | `/api/solicitudes/:id` | Detalle + autorizados habilitados |
| PUT | `/api/solicitudes/:id` | Edita (borra las firmas existentes) |
| DELETE | `/api/solicitudes/:id` | Elimina |
| POST | `/api/solicitudes/:id/autorizar` | Registra una firma (`autorizado_id` + `pin`) |
| POST | `/api/solicitudes/:id/revisar` | Devuelve (`accion: observar`) o rechaza (`accion: rechazar`), con `autorizado_id`, `pin` y `motivo` |
| DELETE | `/api/solicitudes/:id/autorizaciones/:aid` | Deshace una firma |
| GET | `/api/solicitudes/:id/pdf` | Formulario oficial completado |
| GET | `/api/solicitudes/:id/factura` | Factura original adjunta |
| GET | `/api/autorizados` | Listado de autorizados (filtro: `lista`) |
| POST | `/api/autorizados/:id/pin` | Alta o cambio de PIN |

## Avisos por mail

Avisos automáticos, cada uno en un momento del circuito:

| Cuándo | A quién | Qué dice |
|---|---|---|
| Se carga un gasto (queda **pendiente**) | Solo el firmante que eligió quien cargó el gasto | Hay una AGC esperando su firma; el gasto no avanza hasta que alguien autorice |
| Se cambia el firmante, o se corrige una que había **devuelto** | El firmante (el nuevo, o el que la devolvió) | La tiene para firmar |
| Pasan **48 h** sin firmarla, y otra vez **una semana** después de ese recordatorio | El firmante | Recordatorio. Ahí se corta: son tres mails como máximo |
| La última firma la deja **autorizada** | La cajera de cada razón social imputada, según la ubicación (Rosario / Santa Fe) | Ya se puede gestionar el pago |

Los **recordatorios** (`server/services/recordatorios.py`) los revisa la propia app cada
15 minutos; no hace falta un cron. Salen solo en días hábiles de 8 a 18 (si el plazo se
cumple de noche o un fin de semana, sale el próximo día hábil a las 8; los feriados no se
contemplan). Cuentan desde que le toca firmar a la persona actual (el alta, el cambio de
firmante o la corrección). Si a alguien le vencen varias juntas, recibe **un solo mail**
con todas. No se le recuerda a nadie algo que no puede firmar (de baja, otra marca o tope
insuficiente), ni las viejas sin firmante elegido.

Reglas de la implementación (`server/services/avisos.py`):

- El aviso sale **después** de persistir, y es **best-effort**: si el SMTP está caído,
  la carga del gasto igual funciona y el fallo queda en el log.
- **Un mail por destinatario**, nunca un `To:` con todos.
- Sale **una sola vez** por transición: se marca en `solicitudes.notificado_at` y
  `cajeras_notificado_at`. Editar un gasto ya cargado no vuelve a avisar.
- El link va al detalle (`/proceso-compra/solicitudes/:id`), que es donde se firma.
  **No se firma desde el mail**: un link que autoriza sin identificar a la persona es
  una firma sin firmante. En la app se confirma con el PIN, como siempre.

El transporte es el estándar de las apps de Neostar: SMTP de Gmail contra
`neostar.no.reply@gmail.com`, con una **App Password propia de esta app** (se revoca sin
tumbar las otras). Lo único que cambia el remitente entre apps es `MAIL_FROM_NOMBRE`.
Nunca un `From:` `@neostar.com.ar`: ese dominio está en DMARC `p=reject` y rebota.
**Sin `SMTP_*` configurado la app no manda nada y solo loguea**, así se puede desarrollar
y testear sin cuenta de mail.

### Variables de entorno

| Variable | Rol |
|---|---|
| `APP_NOMBRE` | Nombre público de la app (remitente, asunto, pie). Default: *Autorizaciones de Compra*. |
| `APP_COLOR` | Acento del header y del botón. Default `#2DB84B`. |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.gmail.com` / `587`. |
| `SMTP_USER` | `neostar.no.reply@gmail.com`. Es el `From` real: Gmail reescribe cualquier otro. |
| `SMTP_PASSWORD` | App Password de 16 caracteres, **sin** los espacios de los 4 grupos. |
| `MAIL_FROM_NOMBRE` | Nombre del remitente. Normalmente igual a `APP_NOMBRE`. |
| `MAIL_REPLY_TO` | A dónde van las respuestas. Sin definir, no se manda. |
| `PUBLIC_BASE_URL` | Dominio con el que se arman los links (`http://192.168.41.39`). **Obligatorio en Docker**: detrás de nginx el request dice `backend:5000`. |
| `RECORDATORIOS` | `0` apaga los recordatorios (por ejemplo, en una copia de prueba con mail de verdad). Sin definir, están prendidos. |
| `CAJA_<UBICACION>_<EMPRESA>` (ej. `CAJA_SANTA_FE_HIKARI`, `CAJA_ROSARIO_ALCO_ROSARIO`) | Cajera de cada razón social en cada ubicación, para el aviso de autorizada. |
| `CAJA_ALCO_ROSARIO`, `CAJA_NEOSTAR`, `CAJA_XINOXIA`, `CAJA_DASEOS`, `CAJA_HIKARI` | Cajera por razón social sola: para solicitudes sin ubicación (cargadas antes de que existiera) y razones sociales sin cajera por sede. |

Cajeras por ubicación y razón social (defaults del código):

| | Rosario | Santa Fe |
|---|---|---|
| ALCO ROSARIO S.A. | nblois | mgonzalez |
| NEOSTAR S.A. | mspurello | evanlesberg |
| HIKARI S.A. | bcoll | dmorelli |
| XINOXIA S.A. | mlhenning | mlhenning |
| DASEOS S.A. | mspurello | mspurello |

XINOXIA y DASEOS no tienen cajera por sede: van a la de la razón social, sea cual sea
la ubicación. Una solicitud sin ubicación (anterior a este cambio) avisa por razón
social, que coincide con la columna Rosario.

Las cajeras tienen **default en el código** (`services/avisos.py`), así la app avisa
aunque el `.env` esté pelado. Mover a alguien es tocar el `.env`, no el código; una lista
**vacía** significa "no avisar a nadie". En el compose las variables van **sin `=`**: con
`=${VAR}` se pasarían vacías y pisarían el default.

### A quién le llega el aviso de gasto nuevo

**Lo elige quien carga la solicitud, es obligatorio y es una sola persona.** Al final
del alta aparece *¿Quién firma esta solicitud?* con los autorizados que pueden firmar
ese gasto:

- habilitados para la marca (su planilla o Multimarca; con varias marcas, solo
  Multimarca, igual que para firmar), y
- con tope suficiente para el monto, o sin límite.

Hay que elegir exactamente uno; sin eso la solicitud no se guarda. El mail le llega
exclusivamente a esa persona: sin copias y nunca a toda la planilla. En el detalle de
la solicitud queda quién es el firmante elegido. (Las solicitudes anteriores a este
cambio pueden tener varios avisados; se respetan tal cual.)

**Solo puede firmar el firmante elegido**: en el detalle, en *Para firmar* y en la
firma en lote (`services/autorizacion.py`, `firmar()`). Si otra persona lo intenta, la
firma se rechaza aunque esté habilitada para la marca. Las solicitudes cargadas antes
de que existiera la elección no tienen firmante y las sigue pudiendo firmar cualquier
habilitado.

Si el elegido ya no puede firmar (lo dieron de baja, no está habilitado para la marca, o
le bajaron el tope y ya no cubre el monto), el detalle lo avisa y no lo deja firmar: se
destraba con **Editar**, eligiendo otro firmante. Al nuevo le llega el mail y la firma
desde cero. La firma de conformidad de los pagos imputados no cambia (ahí sigue la
segunda firma cuando el pago supera el tope de quien firma).

El mail de cada autorizado vive en la base y se carga en el panel de **Autorizados**
con la clave de administración. Quien no tiene mail aparece en la lista pero no se
puede tildar. Los mails iniciales están en `EMAILS` de `models/autorizados_seed.py` y
solo se aplican a quien todavía no tiene uno, así que lo corregido en el panel no se
pierde al reiniciar.

Pendiente: filtrar también por **concepto**, cuando administración pase qué
categorías del formulario firma cada autorizado.

### Probar el envío

```bash
cd server
python probar_mail.py                      # a la propia casilla
python probar_mail.py alguien@neostar.com.ar
```

Manda un mail real con el **mismo** `enviar_mail()` de producción y nunca imprime la
contraseña. Si ese llega, los avisos llegan.

## Autorizados

Los 25 autorizados se cargan automáticamente al primer arranque desde
`server/models/autorizados_seed.py`, según las planillas de Sep. 2025
(Nissan, Jeep, Kia, Multimarca). Para actualizarlos se edita ese archivo:
al reiniciar se sincronizan cargos, montos y conceptos sin borrar los PIN.

## Notas

- La app no requiere autenticación de acceso (uso en red interna); el PIN protege
  el acto de autorizar, que es lo que tiene consecuencia.
- Las facturas escaneadas (sin capa de texto) no se pueden leer: la app lo avisa y
  permite cargar los datos a mano.
- **Horas**: desde nov-2026 el contenedor usa la hora de Argentina. Lo guardado antes
  (firmas, cargas, Autopack, eliminaciones) quedó en UTC, con 3 h de más, y se decidió
  no corregirlo.
- Los PDF (autorización, autorización + facturas, ZIP) se arman en memoria en cada
  pedido; no se guardan en disco.
- **Inicio**: la lista viene de a 50, con filtros por estado, razón social, marca,
  ubicación, urgencia y fechas de carga, y se exporta a Excel con esos mismos filtros. La
  columna *Autopack* es de solo lectura; para marcarla, administración entra con su mail
  y la clave ("Soy de administración: marcar Autopack").
