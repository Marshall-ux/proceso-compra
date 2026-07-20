import { useEffect, useState } from 'react'
import { LISTAS, fmtMoney } from '../constants.js'
import { autorizarLote, listarAutorizados } from '../services/api.js'

// Firma varias solicitudes de una vez: el PIN se pide una sola vez, pero las reglas
// (marca habilitada, no firmar dos veces) se aplican solicitud por solicitud, así que
// puede que algunas se salteen y se informa el motivo.
export default function PanelLote({ solicitudes, onListo }) {
  const [autorizados, setAutorizados] = useState([])
  const [elegido, setElegido] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [salteadas, setSalteadas] = useState([])
  const [enviando, setEnviando] = useState(false)

  useEffect(() => { listarAutorizados().then(setAutorizados) }, [])

  const persona = autorizados.find((a) => String(a.id) === String(elegido))
  const total = solicitudes.reduce((acc, s) => acc + (Number(s.monto_total) || 0), 0)

  const firmar = async () => {
    setError(''); setSalteadas([])
    if (!elegido) return setError('Elegí quién autoriza')
    if (!pin) return setError('Ingresá el PIN')

    setEnviando(true)
    try {
      const r = await autorizarLote({
        autorizado_id: Number(elegido),
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
    <div className="card" style={{ background: 'var(--bg-alt)', marginBottom: '1.2rem' }}>
      <div className="card__title" style={{ fontSize: '1rem' }}>
        ✍️ Autorizar {solicitudes.length} solicitud(es) juntas
      </div>
      <div className="card__hint">
        Total ${' '}{fmtMoney(total)}. Las que no correspondan a tu marca o ya hayas firmado
        se saltean y te aviso cuáles.
      </div>

      {error && <div className="alert alert--error">{error}</div>}

      <div className="grid grid--2">
        <div className="field">
          <label>Autorizante</label>
          <select value={elegido} onChange={(e) => { setElegido(e.target.value); setError('') }}>
            <option value="">Elegí quién autoriza…</option>
            {autorizados.map((a) => (
              <option key={a.id} value={a.id} disabled={a.bloqueado}>
                {a.nombre} · {LISTAS[a.lista] || a.lista}
                {a.sin_limite ? ' · sin límite' : ` · hasta $ ${fmtMoney(a.monto_autorizado)}`}
                {a.bloqueado ? ' · BLOQUEADO' : ''}
                {!a.tiene_pin ? ' · sin PIN' : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>PIN</label>
          <div style={{ display: 'flex', gap: '0.6rem' }}>
            <input
              className="pin-input" type="password" inputMode="numeric" maxLength={8}
              value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
              onKeyDown={(e) => e.key === 'Enter' && firmar()}
              style={{ flex: 1 }}
            />
            <button className="btn btn--primary" onClick={firmar} disabled={enviando}>
              {enviando ? <span className="spinner" /> : 'Autorizar todas'}
            </button>
          </div>
        </div>
      </div>

      {persona && !persona.tiene_pin && (
        <div className="alert alert--info" style={{ marginTop: '0.9rem' }}>
          {persona.nombre} todavía no definió su PIN. Tiene que hacerlo desde una solicitud
          individual, con el código de alta que entrega administración.
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
