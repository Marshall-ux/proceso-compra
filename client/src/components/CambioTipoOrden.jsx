import { useState } from 'react'
import { fmtFechaHora } from '../constants.js'
import { cambiarTipoOrden } from '../services/api.js'

// Pasar una solicitud pendiente a orden abierta o cerrada. Solo lo hacen los habilitados
// (hoy Raúl García), con su PIN; queda registrado quién y cuándo.
export default function CambioTipoOrden({ solicitud, onActualizar }) {
  const habilitados = solicitud.habilitados_tipo_orden || []
  const [abierto, setAbierto] = useState(false)
  const [autorizadoId, setAutorizadoId] = useState('')
  const [duracion, setDuracion] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  if (habilitados.length === 0) return null

  const esAbierta = solicitud.tipo_orden === 'abierta'
  const destino = esAbierta ? 'cerrada' : 'abierta'
  const firmas = solicitud.autorizaciones?.length || 0

  const abrir = () => {
    setAbierto(true); setError(''); setPin(''); setDuracion('')
    setAutorizadoId(habilitados.length === 1 ? String(habilitados[0].id) : '')
  }

  const confirmar = async () => {
    setError('')
    if (!autorizadoId) return setError('Elegí quién hace el cambio.')
    if (destino === 'abierta' && !duracion.trim()) return setError('Indicá la duración de la orden abierta.')
    if (!pin) return setError('Ingresá el PIN.')
    setGuardando(true)
    try {
      const s = await cambiarTipoOrden(solicitud.id, {
        autorizado_id: Number(autorizadoId), pin, tipo_orden: destino, duracion_orden: duracion.trim(),
      })
      onActualizar(s)
      setAbierto(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="card">
      <div className="toolbar" style={{ marginBottom: abierto ? '1rem' : 0 }}>
        <div>
          <div className="card__title" style={{ marginBottom: '0.2rem' }}>
            🔁 Tipo de orden: {esAbierta ? 'abierta' : solicitud.tipo_orden === 'cerrada' ? 'cerrada' : 'sin indicar'}
            {esAbierta && solicitud.duracion_orden && <> · {solicitud.duracion_orden}</>}
          </div>
          {solicitud.tipo_orden_por && (
            <div className="card__hint" style={{ marginBottom: 0 }}>
              Cambiado por {solicitud.tipo_orden_por} el {fmtFechaHora(solicitud.tipo_orden_fecha)}
            </div>
          )}
        </div>
        {!abierto && (
          <button className="btn btn--ghost btn--sm" onClick={abrir}>
            Cambiar a orden {destino}
          </button>
        )}
      </div>

      {abierto && (
        <>
          {firmas > 0 && (
            <div className="alert alert--warning">
              Esta solicitud ya tiene {firmas} firma(s). Al cambiar el tipo de orden se borran
              y hay que volver a autorizar: nadie firma algo que después se modificó.
            </div>
          )}
          {error && <div className="alert alert--error">{error}</div>}
          <div className="grid grid--3">
            <div className="field">
              <label>Quién hace el cambio</label>
              <select value={autorizadoId} onChange={(e) => setAutorizadoId(e.target.value)}>
                {habilitados.length > 1 && <option value="">Elegí…</option>}
                {habilitados.map((h) => (
                  <option key={h.id} value={h.id} disabled={!h.tiene_pin}>
                    {h.nombre}{!h.tiene_pin ? ' · sin PIN' : ''}
                  </option>
                ))}
              </select>
            </div>
            {destino === 'abierta' && (
              <div className="field">
                <label>Duración de la orden abierta</label>
                <input type="text" placeholder="Ej: 6 meses" value={duracion}
                       onChange={(e) => setDuracion(e.target.value)} />
              </div>
            )}
            <div className="field">
              <label>PIN</label>
              <input
                className="pin-input" type="password" inputMode="numeric" maxLength={8}
                value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
                onKeyDown={(e) => e.key === 'Enter' && confirmar()}
              />
            </div>
          </div>
          <div className="toolbar" style={{ marginBottom: 0 }}>
            <button className="btn btn--ghost" onClick={() => setAbierto(false)}>Cancelar</button>
            <button className="btn btn--primary" onClick={confirmar} disabled={guardando}>
              {guardando ? <><span className="spinner" /> Guardando…</> : `Pasar a orden ${destino}`}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
