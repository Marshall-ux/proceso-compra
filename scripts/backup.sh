#!/bin/sh
# Backup diario de proceso-compra: la base y los adjuntos. Lo corre el cron del servidor
# (ver "Backups" en el README). Solo lee la app: nunca la frena ni la modifica.
#
# - Base: copia en caliente con la API de backup de SQLite (queda consistente aunque
#   alguien esté firmando en ese momento), verificada y comprimida. Se guardan $DIAS días.
# - Adjuntos: espejo de server/uploads/. Un adjunto no cambia una vez subido, así que solo
#   se copian los nuevos, y del espejo nunca se borra nada.
set -eu

APP_DIR=${APP_DIR:-/opt/portal/portal-interno/proceso-compra}
DESTINO=${DESTINO:-/opt/portal/portal-interno/proceso-compra-backups/automaticos}
CONTENEDOR=${CONTENEDOR:-proceso-compra-backend-1}
DIAS=${DIAS:-30}

# El servidor está en UTC: el nombre del archivo va con la hora de Argentina.
ahora() { TZ=America/Argentina/Buenos_Aires date "$@"; }
FECHA=$(ahora +%Y%m%d-%H%M)
mkdir -p "$DESTINO/base" "$DESTINO/adjuntos"

docker exec "$CONTENEDOR" python -c "
import os, sqlite3
if os.path.exists('/tmp/backup.db'):
    os.remove('/tmp/backup.db')
copia = sqlite3.connect('/tmp/backup.db')
sqlite3.connect('/app/data/app.db').backup(copia)
resultado = copia.execute('pragma integrity_check').fetchone()[0]
assert resultado == 'ok', 'la copia no pasó el chequeo de integridad: ' + resultado
"
docker cp "$CONTENEDOR:/tmp/backup.db" "$DESTINO/base/app-$FECHA.db"
docker exec "$CONTENEDOR" rm -f /tmp/backup.db
gzip -f "$DESTINO/base/app-$FECHA.db"

nuevos=0
for archivo in "$APP_DIR/server/uploads"/*; do
    [ -f "$archivo" ] || continue
    nombre=$(basename "$archivo")
    if [ ! -e "$DESTINO/adjuntos/$nombre" ]; then
        cp -p "$archivo" "$DESTINO/adjuntos/$nombre"
        nuevos=$((nuevos + 1))
    fi
done

find "$DESTINO/base" -name 'app-*.db.gz' -mtime +"$DIAS" -delete

echo "$(ahora '+%Y-%m-%d %H:%M') ok: base app-$FECHA.db.gz, $nuevos adjuntos nuevos"
