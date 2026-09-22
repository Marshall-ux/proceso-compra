# Autorizaciones de Compra · Neostar

Aplicación web que automatiza el circuito de autorización de compras: se sube la
factura del proveedor, se extraen sus datos, se completa el formulario oficial
**F 8.4-01 · Autorización Genérica de Compra o Contratación (Rev. 07)** y dos
autorizados firman digitalmente.

## Cómo funciona

1. **Subir factura** — se lee el PDF y se extraen proveedor, CUIT, fecha, importes,
   condiciones de pago, contacto y el detalle de ítems.
2. **Revisar y completar** — los campos leídos de la factura se muestran resaltados.
   El empleado completa lo que la factura no dice (marca, concepto, tipo de orden,
   quién solicita).
3. **Autorizar** — se elige a cada autorizante de la lista y confirma con su PIN.
   **Hacen falta dos personas distintas**; con una sola el proceso no se completa.
4. **PDF** — se descarga el formulario oficial completado, con los dos autorizantes
   y la fecha/hora de cada firma.

## Stack

- **Frontend**: React + Vite (JavaScript), CSS vanilla (estética Neostar, tema claro)
- **Backend**: Python 3.12 + Flask, pdfplumber (lectura), pypdf + reportlab (llenado)
- **Base de datos**: SQLite
- **Despliegue**: Docker (backend Flask + frontend Nginx)

## Reglas del proceso

- **Dos autorizantes distintos** por solicitud. La misma persona no puede firmar dos veces.
- **PIN por persona**: cada autorizado define su PIN la primera vez que firma. Se guarda
  hasheado (PBKDF2-SHA256), nunca en claro.
- **Marca**: sólo pueden firmar los autorizados habilitados para esa marca.
  Los de **Multimarca** pueden autorizar cualquiera; la planilla de **Kia** cubre también
  Suzuki y la de **Jeep** corresponde a FCA / Chrysler.
- **Topes**: si el monto supera el tope de la persona, se avisa pero se permite firmar,
  y queda registrado en el PDF. Los directores figuran *sin límite*.
- **Edición**: si se edita una solicitud ya firmada, las firmas se borran y hay que
  volver a autorizar. Una autorizada no se puede modificar.

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
- El original tiene un único recuadro "AUTORIZADO POR"; como el proceso exige dos
  firmas, ese recuadro se divide en dos mitades.

Si sale un **Rev. 08**: reemplazar el PDF de `server/assets/` y revisar el mapa de
campos en `services/pdf_fill.py`.

## Estructura

```
client/          Frontend React + Vite
server/          Backend Flask (routes, services, models)
  assets/        Formulario oficial F 8.4-01 + logo
  services/      extractor.py (lee facturas) · pdf_fill.py (completa el formulario)
docs/            Documentación fuente (formulario, planillas de autorizados, factura ejemplo)
```

## Desarrollo con Docker (recomendado)

Requiere Docker Desktop corriendo.

```bash
docker-compose up --build      # construir y levantar
docker-compose up -d           # en segundo plano
docker-compose down            # detener
docker-compose logs -f backend # ver logs del backend
```

- Frontend: http://localhost:8092/proceso-compra/
- Backend API: http://localhost:8092/proceso-compra/api

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
| GET | `/api/solicitudes` | Lista (filtros: `estado`, `q`) |
| POST | `/api/solicitudes` | Crea |
| GET | `/api/solicitudes/:id` | Detalle + autorizados habilitados |
| PUT | `/api/solicitudes/:id` | Edita (borra las firmas existentes) |
| DELETE | `/api/solicitudes/:id` | Elimina |
| POST | `/api/solicitudes/:id/autorizar` | Registra una firma (`autorizado_id` + `pin`) |
| DELETE | `/api/solicitudes/:id/autorizaciones/:aid` | Deshace una firma |
| GET | `/api/solicitudes/:id/pdf` | Formulario oficial completado |
| GET | `/api/solicitudes/:id/factura` | Factura original adjunta |
| GET | `/api/autorizados` | Listado de autorizados (filtro: `lista`) |
| POST | `/api/autorizados/:id/pin` | Alta o cambio de PIN |

## Avisos por mail

Dos avisos automáticos, cada uno en una transición del circuito:

| Cuándo | A quién | Qué dice |
|---|---|---|
| Se carga un gasto (queda **pendiente**) | Los autorizantes habilitados para esa marca | Hay una AGC esperando firma; el gasto no avanza hasta que alguien autorice |
| La última firma la deja **autorizada** | La cajera de cada razón social imputada | Ya se puede gestionar el pago |

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
| `AUTORIZA_NOTIF_EMAIL` | Copia fija que recibe todos los avisos de gasto nuevo, sea de la marca que sea. |
| `CAJA_ALCO_ROSARIO`, `CAJA_NEOSTAR`, `CAJA_XINOXIA`, `CAJA_DASEOS`, `CAJA_HIKARI` | Cajera de cada razón social, para el aviso de autorizada. |

Las cajeras tienen **default en el código** (`services/avisos.py`), así la app avisa
aunque el `.env` esté pelado. Mover a alguien es tocar el `.env`, no el código; una lista
**vacía** significa "no avisar a nadie". En el compose las variables van **sin `=`**: con
`=${VAR}` se pasarían vacías y pisarían el default.

### A quién le llega el aviso de gasto nuevo

**Lo elige quien carga la solicitud, y es obligatorio.** Al final del alta aparece
*¿A quién le avisamos?* con los autorizados que pueden firmar ese gasto:

- habilitados para la marca (su planilla o Multimarca; con varias marcas, solo
  Multimarca, igual que para firmar), y
- con tope suficiente para el monto, o sin límite.

Hay que tildar al menos uno; sin eso la solicitud no se guarda. El mail les llega solo
a los tildados (más la copia de `AUTORIZA_NOTIF_EMAIL`), nunca a toda la planilla. En el
detalle de la solicitud queda a quién se le avisó.

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
