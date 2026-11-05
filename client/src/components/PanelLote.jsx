import { useState } from 'react'
import { fmtMoney, montoEnPesos } from '../constants.js'
import { autorizarLote } from '../services/api.js'

// Firma de una vez todo lo que tiene para firmar `persona` (la que eligió su nombre en
// "Para firmar"). El PIN se pide una sola vez, pero las reglas se aplican solicitud por
// solicitud: si alguna no se puede firmar se saltea y se informa el motivo.
export default function PanelLote({ solicitudes, persona, onListo, onCancelar }) {
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [salteadas, setSalteadas] = useState([])
  const [enviando, setEnviando] = useState(false)

  // Puede haber solicitudes en dólares: el total se muestra en pesos.
  const total = solicitudes.reduce((acc, s) => acc + montoEnPesos(s.monto_total, s.moneda, s.tipo_cambio), 0)
  const hayDolares = solicitudes.some((s) => s.moneda === 'USD')

  const firmar = async () => {
    setError(''); setSalteadas([])
    if (!pin) return setError('Ingresá el PIN')

    setEnviando(true)
    try {
      const r = await autorizarLote({
        autorizado_id: Number(persona.id),
        pin,
        ids: solicitudes.map((s) => s.id),
      })
      setPin('')
      setSalteadas(r.salteadas || [])
      if ((r.salteadas || []).length === 0) onListo(r)
      else onListo({ ...r, resumen: `${r.resumen} Mirá abajo las que no se pudieron firmar.` })
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="card" style={{ background: 'var(--surface)', marginTop: '0.9rem' }}>
      <div className="card__title" style={{ fontSize: '1rem' }}>
        ✍️ Firmar las {solicitudes.length} como {persona.nombre}
      </div>
      <div className="card__hint">
        Total $ {fmtMoney(total)}{hayDolares && ' (las de dólares, convertidas a pesos)'}. Firmarlas acá
        es lo mismo que firmar cada una desde su detalle: revisalas antes.
      </div>

      {error && <div className="alert alert--error">{error}</div>}

      {!persona.tiene_pin ? (
        <div className="alert alert--info">
          Todavía no definiste tu PIN. Hacelo desde una solicitud individual, con el código de
          alta que entrega administración.
        </div>
      ) : (
        <div className="pin-box" style={{ marginTop: 0 }}>
          <div className="field">
            <label>Tu PIN</label>
            <input
              className="pin-input" type="password" inputMode="numeric" maxLength={8} autoFocus
              value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
              onKeyDown={(e) => e.key === 'Enter' && firmar()}
            />
          </div>
          <button className="btn btn--primary" onClick={firmar} disabled={enviando}>
            {enviando ? <span className="spinner" /> : `Firmar las ${solicitudes.length}`}
          </button>
          <button className="btn btn--ghost" onClick={onCancelar} disabled={enviando}>Cancelar</button>
        </div>
      )}

      {salteadas.length > 0 && (
        <div className="alert alert--warning" style={{ marginTop: '0.9rem' }}>
          No se pudieron firmar:
          <ul>
            {salteadas.map((s) => <li key={s.id}>Solicitud #{s.id}: {s.motivo}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}
