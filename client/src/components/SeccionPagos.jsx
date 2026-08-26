import { useRef, useState } from 'react'
import { LISTAS, fmtFechaHora, fmtMoney } from '../constants.js'
import {
  crearPago, eliminarPago, extraerFacturas, firmarPago, urlFactura,
} from '../services/api.js'

// Pagos imputados a una AGC autorizada. La AGC controla el presupuesto; cada pago se
// firma como conformidad (misma regla que la AGC: 1 firma dentro del tope, 2 si lo supera).
export default function SeccionPagos({ solicitud, onActualizar }) {
  const inputRef = useRef(null)
  const [agregando, setAgregando] = useState(false)
  const [subiendo, setSubiendo] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [nuevo, setNuevo] = useState(vacio())
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [firmando, setFirmando] = useState(null)   // { pagoId, autorizadoId, pin }

  const pagos = solicitud.pagos || []
  const r = solicitud.pagos_resumen || {}
  const disponibles = solicitud.autorizados_disponibles || []

  function vacio() {
    return { descripcion: '', monto: '', fecha: '', cargado_por: '', facturas: [] }
  }

  const subirFacturas = async (fileList) => {
    const lista = Array.from(fileList || [])
    if (lista.length === 0) return
    setSubiendo(true); setError('')
    try {
      const res = await extraerFacturas(lista)
      setNuevo((n) => ({
        ...n,
        facturas: res.facturas || [],
        monto: n.monto || res.datos?.monto_total || '',
        fecha: n.fecha || res.datos?.fecha || '',
      }))
    } catch (e) {
      setError(e.message)
    } finally {
      setSubiendo(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const guardarPago = async () => {
    setError('')
    if (!nuevo.descripcion.trim()) return setError('Poné una descripción (ej: "avance 20%").')
    if (!(Number(nuevo.monto) > 0)) return setError('El monto debe ser mayor a cero.')
    setGuardando(true)
    try {
      const s = await crearPago(solicitud.id, {
        descripcion: nuevo.descripcion.trim(),
        monto: Number(nuevo.monto),
        fecha: nuevo.fecha.trim(),
        cargado_por: nuevo.cargado_por.trim(),
        facturas: nuevo.facturas,
      })
      onActualizar(s)
      setNuevo(vacio()); setAgregando(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  const firmar = async (pago) => {
    setError(''); setAviso('')
    const f = firmando || {}
    if (!f.autorizadoId) return setError('Elegí quién da la conformidad.')
    if (!f.pin) return setError('Ingresá el PIN.')
    try {
      const s = await firmarPago(solicitud.id, pago.id, {
        autorizado_id: Number(f.autorizadoId), pin: f.pin,
      })
      setAviso(s.aviso_tope || '')
      setFirmando(null)
      onActualizar(s)
    } catch (e) {
      setError(e.data?.mensaje || e.message)
    }
  }

  const borrar = async (pago) => {
    if (!confirm(`¿Eliminar el pago "${pago.descripcion}"?`)) return
    setError('')
    try {
      onActualizar(await eliminarPago(solicitud.id, pago.id))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="card">
      <div className="card__title">💸 Pagos imputados a esta AGC</div>
      <div className="card__hint">
        La AGC controla el presupuesto; cada factura/pago se firma como conformidad de que
        el servicio o avance se dio. No re-autoriza la AGC.
      </div>

      {/* Resumen presupuesto vs imputado */}
      <div className="pagos-resumen">
        <div><span className="pagos-resumen__lab">Presupuesto</span><strong>$ {fmtMoney(r.presupuesto)}</strong></div>
        <div><span className="pagos-resumen__lab">Imputado</span><strong>$ {fmtMoney(r.imputado)}</strong></div>
        {!r.abierta && (
          <div><span className="pagos-resumen__lab">Saldo</span>
            <strong style={{ color: r.saldo < 0 ? 'var(--danger)' : 'var(--text)' }}>$ {fmtMoney(r.saldo)}</strong>
          </div>
        )}
        {r.abierta && <div className="badge badge--info">Orden abierta (tarifario de referencia)</div>}
      </div>
      {r.excede && (
        <div className="alert alert--warning">
          Lo imputado (${fmtMoney(r.imputado)}) <strong>supera el presupuesto</strong> de la AGC
          (${fmtMoney(r.presupuesto)}). Revisalo.
        </div>
      )}

      {error && <div className="alert alert--error">{error}</div>}
      {aviso && <div className="alert alert--warning">{aviso}</div>}

      {/* Lista de pagos */}
      {pagos.length === 0 ? (
        <div className="empty" style={{ padding: '1.5rem' }}>Todavía no hay pagos imputados.</div>
      ) : (
        <div className="pagos-lista">
          {pagos.map((p) => {
            const conforme = p.estado === 'conforme'
            return (
              <div key={p.id} className={`pago ${conforme ? 'pago--conforme' : ''}`}>
                <div className="pago__head">
                  <div>
                    <strong>{p.descripcion || 'Pago'}</strong>
                    {p.fecha && <span className="pago__fecha"> · {p.fecha}</span>}
                    <div className="pago__meta">
                      {p.facturas.map((f) => (
                        <a key={f.id} href={urlFactura(solicitud.id, f.id)} target="_blank"
                           rel="noreferrer" className="link-factura">📄 factura</a>
                      ))}
                      {p.cargado_por && <span> · cargó {p.cargado_por}</span>}
                    </div>
                  </div>
                  <div className="pago__monto">
                    $ {fmtMoney(p.monto)}
                    <div>
                      {conforme
                        ? <span className="badge badge--success">Conforme</span>
                        : <span className="badge badge--warning">
                            {p.requiere_segunda_firma ? 'Falta 2ª firma' : 'Pendiente'}
                          </span>}
                    </div>
                  </div>
                </div>

                {/* Firmas del pago */}
                {p.firmas.length > 0 && (
                  <div className="pago__firmas">
                    {p.firmas.map((fi) => (
                      <span key={fi.id} className="pago__firma">
                        ✓ {fi.nombre} · {fmtFechaHora(fi.fecha)}
                        {!!fi.excedio_tope && <em> (excedió su tope)</em>}
                      </span>
                    ))}
                  </div>
                )}

                {/* Firmar conformidad / eliminar (solo si pendiente) */}
                {!conforme && (
                  <div className="pago__acciones">
                    {firmando?.pagoId === p.id ? (
                      <div className="pago__firmar">
                        <select
                          value={firmando.autorizadoId || ''}
                          onChange={(e) => setFirmando({ ...firmando, autorizadoId: e.target.value })}
                        >
                          <option value="">Quién da la conformidad…</option>
                          {disponibles.map((a) => (
                            <option key={a.id} value={a.id} disabled={a.bloqueado || !a.tiene_pin}>
                              {a.nombre} · {LISTAS[a.lista] || a.lista}
                              {a.sin_limite ? ' · sin límite' : ` · hasta $ ${fmtMoney(a.monto_autorizado)}`}
                              {!a.tiene_pin ? ' · sin PIN' : ''}{a.bloqueado ? ' · bloqueado' : ''}
                            </option>
                          ))}
                        </select>
                        <input
                          className="pin-input" type="password" inputMode="numeric" maxLength={8}
                          placeholder="PIN" value={firmando.pin || ''}
                          onChange={(e) => setFirmando({ ...firmando, pin: e.target.value.replace(/\D/g, '') })}
                          onKeyDown={(e) => e.key === 'Enter' && firmar(p)}
                        />
                        <button className="btn btn--primary btn--sm" onClick={() => firmar(p)}>Firmar</button>
                        <button className="btn btn--ghost btn--sm" onClick={() => setFirmando(null)}>Cancelar</button>
                      </div>
                    ) : (
                      <>
                        <button className="btn btn--primary btn--sm"
                                onClick={() => setFirmando({ pagoId: p.id, autorizadoId: '', pin: '' })}>
                          ✍️ Firmar conformidad
                        </button>
                        <button className="btn btn--danger btn--sm" onClick={() => borrar(p)}>Eliminar</button>
                      </>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Agregar pago */}
      {agregando ? (
        <div className="pago-nuevo">
          <div className="seccion__titulo">Nuevo pago</div>
          <div className="field">
            <label>Factura(s) del pago (PDF)</label>
            <button type="button" className="btn btn--ghost btn--sm"
                    onClick={() => inputRef.current?.click()} disabled={subiendo}>
              {subiendo ? <><span className="spinner spinner--dark" /> Leyendo…</> : '📎 Subir factura(s)'}
            </button>
            {nuevo.facturas.length > 0 && (
              <div className="field__nota">{nuevo.facturas.length} factura(s): {nuevo.facturas.map((f) => f.nombre).join(', ')}</div>
            )}
            <input ref={inputRef} type="file" accept="application/pdf" multiple
                   style={{ display: 'none' }} onChange={(e) => subirFacturas(e.target.files)} />
          </div>
          <div className="grid grid--3">
            <div className="field">
              <label>Descripción</label>
              <input type="text" placeholder='Ej: "avance 20%"' value={nuevo.descripcion}
                     onChange={(e) => setNuevo({ ...nuevo, descripcion: e.target.value })} />
            </div>
            <div className="field">
              <label>Monto</label>
              <input type="number" step="0.01" value={nuevo.monto}
                     onChange={(e) => setNuevo({ ...nuevo, monto: e.target.value })} />
            </div>
            <div className="field">
              <label>Fecha</label>
              <input type="text" placeholder="dd/mm/aaaa" value={nuevo.fecha}
                     onChange={(e) => setNuevo({ ...nuevo, fecha: e.target.value })} />
            </div>
          </div>
          <div className="field">
            <label>Tu nombre (quién carga)</label>
            <input type="text" value={nuevo.cargado_por}
                   onChange={(e) => setNuevo({ ...nuevo, cargado_por: e.target.value })} />
          </div>
          <div className="toolbar" style={{ marginBottom: 0 }}>
            <button className="btn btn--ghost" onClick={() => { setAgregando(false); setNuevo(vacio()); setError('') }}>
              Cancelar
            </button>
            <button className="btn btn--primary" onClick={guardarPago} disabled={guardando}>
              {guardando ? <><span className="spinner" /> Guardando…</> : 'Agregar pago'}
            </button>
          </div>
        </div>
      ) : (
        <button className="btn btn--primary" style={{ marginTop: '1rem' }} onClick={() => setAgregando(true)}>
          + Agregar pago
        </button>
      )}
    </div>
  )
}
