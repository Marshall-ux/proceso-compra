import { useState } from 'react'
import { LISTAS, fmtMoney } from '../constants.js'
import { autorizar } from '../services/api.js'

// Panel de firmas: el proceso exige DOS autorizantes distintos.
export default function PanelAutorizacion({ solicitud, onActualizar }) {
  const [elegido, setElegido] = useState(null)
  const [pin, setPin] = useState('')
  const [pinNuevo, setPinNuevo] = useState('')
  const [pinRepetido, setPinRepetido] = useState('')
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [enviando, setEnviando] = useState(false)

  const disponibles = solicitud.autorizados_disponibles || []
  const firmas = solicitud.autorizaciones || []
  const completa = solicitud.estado === 'autorizada'
  const primerUso = elegido && !elegido.tiene_pin

  const limpiar = () => {
    setElegido(null); setPin(''); setPinNuevo(''); setPinRepetido(''); setError('')
  }

  const elegir = (a) => {
    setElegido(a); setPin(''); setPinNuevo(''); setPinRepetido(''); setError(''); setAviso('')
  }

  const firmar = async () => {
    setError('')
    if (primerUso) {
      if (!/^\d{4,6}$/.test(pinNuevo)) return setError('El PIN debe tener entre 4 y 6 dígitos')
      if (pinNuevo !== pinRepetido) return setError('Los PIN no coinciden')
    } else if (!pin) {
      return setError('Ingresá tu PIN')
    }

    setEnviando(true)
    try {
      const r = await autorizar(solicitud.id, {
        autorizado_id: elegido.id,
        ...(primerUso ? { pin_nuevo: pinNuevo } : { pin }),
      })
      setAviso(r.aviso_tope || '')
      limpiar()
      onActualizar(r)
    } catch (e) {
      setError(e.data?.mensaje || e.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="card">
      <div className="card__title">
        ✍️ Autorización
        {completa
          ? <span className="badge badge--success">Completa</span>
          : <span className="badge badge--warning">Falta{solicitud.autorizaciones_faltantes > 1 ? 'n' : ''} {solicitud.autorizaciones_faltantes} firma{solicitud.autorizaciones_faltantes > 1 ? 's' : ''}</span>}
      </div>
      <div className="card__hint">
        Se necesitan <strong>dos personas distintas</strong> para completar el proceso.
      </div>

      <div className="firmas">
        {[0, 1].map((i) => {
          const f = firmas[i]
          return (
            <div key={i} className={`firma ${f ? 'firma--completa' : ''}`}>
              <div className="firma__slot">Autorizante {i + 1}</div>
              {f ? (
                <>
                  <div className="firma__nombre">{f.nombre}</div>
                  <div className="firma__cargo">{f.cargo}</div>
                  <div className="firma__fecha">{f.fecha}</div>
                  {!!f.excedio_tope && (
                    <div className="badge badge--warning" style={{ marginTop: '0.4rem' }}>
                      Excedió su tope de $ {fmtMoney(f.monto_tope)}
                    </div>
                  )}
                </>
              ) : (
                <div className="firma__vacia">Pendiente</div>
              )}
            </div>
          )
        })}
      </div>

      {aviso && <div className="alert alert--warning">{aviso}</div>}

      {completa ? (
        <div className="alert alert--ok">
          Proceso completo: la autorización quedó firmada por {firmas.length} personas y el PDF ya está disponible.
        </div>
      ) : (
        <>
          <div className="card__hint" style={{ marginBottom: '0.7rem' }}>
            Autorizados habilitados para <strong>{solicitud.marca}</strong> por un monto de{' '}
            <strong>$ {fmtMoney(solicitud.monto_total)}</strong>:
          </div>

          {error && <div className="alert alert--error">{error}</div>}

          <div className="autorizados-lista">
            {disponibles.map((a) => (
              <button
                type="button"
                key={a.id}
                className={`autorizado ${elegido?.id === a.id ? 'autorizado--elegido' : ''}`}
                disabled={a.ya_firmo}
                onClick={() => elegir(a)}
                title={a.conceptos}
              >
                <div className="autorizado__info">
                  <div className="autorizado__nombre">
                    {a.nombre}{' '}
                    <span className="badge badge--muted">{LISTAS[a.lista] || a.lista}</span>
                    {a.ya_firmo && <span className="badge badge--success"> ya firmó</span>}
                  </div>
                  <div className="autorizado__cargo">{a.cargo}</div>
                  <div className="autorizado__conceptos">{a.conceptos}</div>
                </div>
                <div
                  className="autorizado__tope"
                  style={{ color: a.excede_tope ? 'var(--warning)' : 'var(--text-soft)' }}
                >
                  {a.sin_limite ? 'Sin límite' : `$ ${fmtMoney(a.monto_autorizado)}`}
                  {a.excede_tope && <div style={{ fontSize: '0.68rem' }}>excede su tope</div>}
                </div>
              </button>
            ))}
          </div>

          {elegido && (
            <div style={{ marginTop: '1.2rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
              {elegido.excede_tope && (
                <div className="alert alert--warning">
                  El monto supera el tope de {elegido.nombre} ($ {fmtMoney(elegido.monto_autorizado)}).
                  Puede autorizar igual, pero queda registrado en el PDF.
                </div>
              )}
              {primerUso ? (
                <>
                  <div className="alert alert--info">
                    Es la primera vez que <strong>{elegido.nombre}</strong> autoriza. Definí un PIN
                    de 4 a 6 dígitos: te lo vamos a pedir en las próximas autorizaciones.
                  </div>
                  <div className="pin-box">
                    <div className="field">
                      <label>PIN nuevo</label>
                      <input
                        className="pin-input" type="password" inputMode="numeric" maxLength={6}
                        value={pinNuevo} onChange={(e) => setPinNuevo(e.target.value.replace(/\D/g, ''))}
                      />
                    </div>
                    <div className="field">
                      <label>Repetir PIN</label>
                      <input
                        className="pin-input" type="password" inputMode="numeric" maxLength={6}
                        value={pinRepetido} onChange={(e) => setPinRepetido(e.target.value.replace(/\D/g, ''))}
                      />
                    </div>
                    <button className="btn btn--primary" onClick={firmar} disabled={enviando}>
                      {enviando ? <span className="spinner" /> : 'Autorizar'}
                    </button>
                  </div>
                </>
              ) : (
                <div className="pin-box">
                  <div className="field">
                    <label>PIN de {elegido.nombre}</label>
                    <input
                      className="pin-input" type="password" inputMode="numeric" maxLength={6}
                      autoFocus value={pin}
                      onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
                      onKeyDown={(e) => e.key === 'Enter' && firmar()}
                    />
                  </div>
                  <button className="btn btn--primary" onClick={firmar} disabled={enviando}>
                    {enviando ? <span className="spinner" /> : 'Autorizar'}
                  </button>
                  <button className="btn btn--ghost" onClick={limpiar}>Cancelar</button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
