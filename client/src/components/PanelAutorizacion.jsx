import { useState } from 'react'
import { LISTAS, fmtFechaHora, fmtMoney } from '../constants.js'
import { autorizar, definirPin, quitarAutorizacion } from '../services/api.js'

// Panel de firmas: el proceso exige DOS autorizantes distintos.
export default function PanelAutorizacion({ solicitud, onActualizar }) {
  const [elegido, setElegido] = useState(null)
  const [pin, setPin] = useState('')
  const [codigo, setCodigo] = useState('')
  const [pinNuevo, setPinNuevo] = useState('')
  const [pinRepetido, setPinRepetido] = useState('')
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [enviando, setEnviando] = useState(false)

  const disponibles = solicitud.autorizados_disponibles || []
  const firmas = solicitud.autorizaciones || []
  const completa = solicitud.estado === 'autorizada'
  const requiere2 = solicitud.requiere_segunda_firma
  const primerUso = elegido && !elegido.tiene_pin

  const limpiar = () => {
    setElegido(null); setPin(''); setCodigo(''); setPinNuevo(''); setPinRepetido(''); setError('')
  }

  const elegir = (a) => {
    setElegido(a); setPin(''); setCodigo(''); setPinNuevo(''); setPinRepetido('')
    setError(''); setAviso('')
  }

  const quitar = async (f) => {
    setError(''); setAviso('')
    if (!confirm(`¿Quitar la firma de ${f.nombre}? Va a tener que volver a autorizar.`)) return
    try {
      onActualizar(await quitarAutorizacion(solicitud.id, f.id))
    } catch (e) {
      setError(e.message)
    }
  }

  const firmar = async () => {
    setError('')
    let pinAUsar = pin

    if (primerUso) {
      if (!codigo.trim()) return setError('Ingresá el código de alta que te dio administración')
      if (!/^\d{6,8}$/.test(pinNuevo)) return setError('El PIN debe tener entre 6 y 8 dígitos')
      if (pinNuevo !== pinRepetido) return setError('Los PIN no coinciden')
      pinAUsar = pinNuevo
    } else if (!pin) {
      return setError('Ingresá tu PIN')
    }

    setEnviando(true)
    try {
      // Primera vez: se da de alta el PIN con el código y se firma con ese mismo PIN.
      if (primerUso) {
        await definirPin(elegido.id, { codigo: codigo.trim().toUpperCase(), pin_nuevo: pinNuevo })
      }
      const r = await autorizar(solicitud.id, { autorizado_id: elegido.id, pin: pinAUsar })
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
          ? <span className="badge badge--success">Autorizada</span>
          : <span className="badge badge--warning">Pendiente</span>}
      </div>
      <div className="card__hint">
        {completa
          ? 'Autorizada. El PDF ya está disponible.'
          : requiere2
            ? <>El monto <strong>supera el tope</strong> de {firmas[0]?.nombre}: necesita una <strong>segunda firma</strong> de otra persona.</>
            : <>Con una firma <strong>dentro del tope</strong> del autorizante queda autorizada. Si el monto supera su tope, hará falta una segunda.</>}
      </div>

      <div className="firmas">
        {(completa ? firmas : [...firmas, null]).map((f, i) => (
          <div key={i} className={`firma ${f ? 'firma--completa' : ''}`}>
            <div className="firma__slot">
              {f ? `Firma ${i + 1}` : (firmas.length ? 'Segunda firma' : 'Autorización')}
            </div>
            {f ? (
              <>
                <div className="firma__nombre">{f.nombre}</div>
                <div className="firma__cargo">{f.cargo}</div>
                <div className="firma__fecha">{fmtFechaHora(f.fecha)}</div>
                {!!f.excedio_tope && (
                  <div className="badge badge--warning" style={{ marginTop: '0.4rem' }}>
                    Excedió su tope de $ {fmtMoney(f.monto_tope)}
                  </div>
                )}
                {!completa && (
                  <button
                    className="btn btn--danger btn--sm" style={{ marginTop: '0.5rem' }}
                    onClick={() => quitar(f)}
                    title="Deshacer esta firma (por ejemplo, si autorizó por error)"
                  >
                    ✕ Quitar firma
                  </button>
                )}
              </>
            ) : (
              <div className="firma__vacia">{requiere2 ? 'Falta la segunda firma' : 'Pendiente de firma'}</div>
            )}
          </div>
        ))}
      </div>

      {aviso && <div className="alert alert--warning">{aviso}</div>}

      {completa ? (
        <div className="alert alert--ok">
          Autorizada: firmada por {firmas.length} {firmas.length === 1 ? 'persona' : 'personas'} y el PDF ya está disponible.
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
                disabled={a.ya_firmo || a.bloqueado}
                onClick={() => elegir(a)}
                title={a.conceptos}
              >
                <div className="autorizado__info">
                  <div className="autorizado__nombre">
                    {a.nombre}{' '}
                    <span className="badge badge--muted">{LISTAS[a.lista] || a.lista}</span>
                    {a.ya_firmo && <span className="badge badge--success"> ya firmó</span>}
                    {a.bloqueado && (
                      <span className="badge badge--danger"> bloqueado {a.bloqueado_minutos} min</span>
                    )}
                    {!a.tiene_pin && !a.bloqueado && (
                      <span className="badge badge--info"> sin PIN</span>
                    )}
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
                    <strong>{elegido.nombre}</strong> todavía no definió su PIN. Para hacerlo hace
                    falta el <strong>código de alta</strong> que entrega administración: así nadie
                    puede definir el PIN de otra persona. Elegí un PIN de 6 a 8 dígitos, sin
                    secuencias ni dígitos repetidos.
                  </div>
                  <div className="grid grid--3">
                    <div className="field">
                      <label>Código de alta</label>
                      <input
                        type="text" maxLength={8} placeholder="Ej: TF4227RE"
                        style={{ textTransform: 'uppercase', letterSpacing: '0.15em' }}
                        value={codigo} onChange={(e) => setCodigo(e.target.value.toUpperCase())}
                      />
                    </div>
                    <div className="field">
                      <label>PIN nuevo</label>
                      <input
                        className="pin-input" type="password" inputMode="numeric" maxLength={8}
                        value={pinNuevo} onChange={(e) => setPinNuevo(e.target.value.replace(/\D/g, ''))}
                      />
                    </div>
                    <div className="field">
                      <label>Repetir PIN</label>
                      <input
                        className="pin-input" type="password" inputMode="numeric" maxLength={8}
                        value={pinRepetido} onChange={(e) => setPinRepetido(e.target.value.replace(/\D/g, ''))}
                      />
                    </div>
                  </div>
                  <div className="toolbar" style={{ marginTop: '0.9rem', marginBottom: 0 }}>
                    <button className="btn btn--ghost" onClick={limpiar}>Cancelar</button>
                    <button className="btn btn--primary" onClick={firmar} disabled={enviando}>
                      {enviando ? <span className="spinner" /> : 'Definir PIN y autorizar'}
                    </button>
                  </div>
                </>
              ) : (
                <div className="pin-box">
                  <div className="field">
                    <label>PIN de {elegido.nombre}</label>
                    <input
                      className="pin-input" type="password" inputMode="numeric" maxLength={8}
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
