import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PanelLote from '../components/PanelLote.jsx'
import robot1x from '../assets/robot-96.png'
import robot2x from '../assets/robot-192.png'
import robot3x from '../assets/robot-288.png'
import {
  EMPRESAS, LISTAS, MARCAS, UBICACIONES, esperaDesde, estadoDe, fmtFechaHora, fmtImporte,
} from '../constants.js'
import {
  avisarCajera, cerrarSesionAutopack, iniciarSesionAutopack, listarAutorizados, listarSolicitudes,
  marcarAutopack, paraFirmar, sesionAutopack, sinAvisoCajera, urlExcel, urlZipLote,
} from '../services/api.js'

const SIN_FILTROS = {
  q: '', estado: '', empresa: '', marca: '', ubicacion: '', urgente: false, desde: '', hasta: '',
}

export default function HomePage() {
  const navigate = useNavigate()
  // La lista viene de a una página (50), con los filtros aplicados en el servidor.
  const [lista, setLista] = useState({ solicitudes: [], total: 0, pagina: 1, por_pagina: 50 })
  const [filtros, setFiltros] = useState(SIN_FILTROS)
  const [pagina, setPagina] = useState(1)
  const [cargando, setCargando] = useState(true)
  const [seleccion, setSeleccion] = useState([])
  const [mensaje, setMensaje] = useState(null)
  const solicitudes = lista.solicitudes

  // Acceso rápido del firmante (sin login): elige su nombre, el navegador lo recuerda.
  const [autorizados, setAutorizados] = useState([])
  const [firmante, setFirmante] = useState(() => localStorage.getItem('firmante') || '')
  const [misFirmas, setMisFirmas] = useState([])
  // Firmar todas las de "Para firmar" de una vez, con un solo PIN.
  const [firmandoLote, setFirmandoLote] = useState(false)
  const [avisoLote, setAvisoLote] = useState('')

  useEffect(() => { listarAutorizados().then(setAutorizados).catch(() => {}) }, [])

  const cargarMisFirmas = useCallback(async (id) => {
    if (!id) { setMisFirmas([]); return }
    try {
      setMisFirmas(await paraFirmar(id))
    } catch {
      setMisFirmas([])
    }
  }, [])

  useEffect(() => { cargarMisFirmas(firmante) }, [firmante, cargarMisFirmas, lista])

  // Autorizadas a las que no les salió el aviso a la cajera. Las ve cualquiera, para que
  // alguien se entere; mandarlo lo hace administración. Se revisa con cada recarga de la
  // lista, así una firma recién hecha desde acá aparece enseguida si falló.
  const [sinAviso, setSinAviso] = useState([])
  const [avisando, setAvisando] = useState(null)
  const [resultadoAviso, setResultadoAviso] = useState(null)
  useEffect(() => { sinAvisoCajera().then(setSinAviso).catch(() => {}) }, [lista])

  const elegirFirmante = (id) => {
    setFirmante(id)
    setFirmandoLote(false)
    setAvisoLote('')
    if (id) localStorage.setItem('firmante', id)
    else localStorage.removeItem('firmante')
  }

  // Lo que va al servidor (también arma el link del Excel, con los mismos filtros).
  const consulta = { ...filtros, urgente: filtros.urgente ? '1' : '' }
  const hayFiltros = Object.entries(filtros).some(([k, v]) => v !== SIN_FILTROS[k])

  const cargar = useCallback(async () => {
    setCargando(true)
    try {
      setLista(await listarSolicitudes({ ...filtros, urgente: filtros.urgente ? '1' : '', pagina }))
    } finally {
      setCargando(false)
    }
  }, [filtros, pagina])

  useEffect(() => {
    const t = setTimeout(cargar, 250)
    return () => clearTimeout(t)
  }, [cargar])

  // Cambiar un filtro vuelve a la primera página.
  const filtrar = (campo, valor) => {
    setFiltros((f) => ({ ...f, [campo]: valor }))
    setPagina(1)
  }

  const alternar = (id) =>
    setSeleccion((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  const todasElegidas = solicitudes.length > 0 && solicitudes.every((s) => seleccion.includes(s.id))
  const alternarTodas = () => setSeleccion((s) => (todasElegidas
    ? s.filter((id) => !solicitudes.some((x) => x.id === id))
    : [...new Set([...s, ...solicitudes.map((x) => x.id)])]))

  // Autopack lo tilda solo administración: mail + clave, pedidos una vez por pestaña.
  // Para el resto la columna es de solo lectura.
  const [autopack, setAutopack] = useState(sesionAutopack)
  const [loginAutopack, setLoginAutopack] = useState(null)   // {} o { s, valor } que espera el login
  const [apEmail, setApEmail] = useState('')
  const [apClave, setApClave] = useState('')
  const [apError, setApError] = useState('')
  const [apEntrando, setApEntrando] = useState(false)

  const actualizarFila = (id, cambios) => setLista((l) => ({
    ...l, solicitudes: l.solicitudes.map((x) => (x.id === id ? { ...x, ...cambios } : x)),
  }))

  // El tilde se guarda al instante; se refleja localmente para no recargar todo.
  const guardarAutopack = async (s, valor) => {
    actualizarFila(s.id, { autopack_ok: valor ? 1 : 0 })
    try {
      const r = await marcarAutopack(s.id, valor)
      actualizarFila(s.id, { autopack_por: r.autopack_por, autopack_fecha: r.autopack_fecha })
    } catch (e) {
      cargar()
      if (e.status === 401) {
        // La clave cambió o la sesión quedó vieja: se vuelve a pedir.
        cerrarSesionAutopack()
        setAutopack(null)
        setLoginAutopack({ s, valor })
      } else {
        setMensaje({ tipo: 'error', texto: e.message })
      }
    }
  }

  // "Avisar a la cajera": sin la sesión de administración, primero la pide (y después lo
  // manda solo). Se lee la sesión guardada y no el estado, que recién se actualiza al login.
  const mandarAviso = async (s) => {
    setResultadoAviso(null)
    if (!sesionAutopack()) {
      setApError('')
      setLoginAutopack({ avisar: s })
      return
    }
    setAvisando(s.id)
    try {
      const r = await avisarCajera(s.id)
      setResultadoAviso({
        tipo: 'ok',
        texto: r.destinatarios.length
          ? `Listo: la #${s.id} le avisó a ${r.destinatarios.join(', ')}.`
          : `La #${s.id} no tiene cajera configurada para su razón social: quedó como avisada, sin mail.`,
      })
    } catch (err) {
      if (err.status === 401) {
        cerrarSesionAutopack()
        setAutopack(null)
        setApError('')
        setLoginAutopack({ avisar: s })
      } else {
        setResultadoAviso({ tipo: 'error', texto: err.message })
      }
    } finally {
      setAvisando(null)
      sinAvisoCajera().then(setSinAviso).catch(() => {})
    }
  }

  const entrarAutopack = async (e) => {
    e.preventDefault()
    setApEntrando(true)
    setApError('')
    try {
      const sesion = await iniciarSesionAutopack(apEmail.trim(), apClave)
      setAutopack(sesion)
      setApClave('')
      const pendiente = loginAutopack
      setLoginAutopack(null)
      if (pendiente?.s) guardarAutopack(pendiente.s, pendiente.valor)
      if (pendiente?.avisar) mandarAviso(pendiente.avisar)
    } catch (err) {
      setApError(err.message)
    } finally {
      setApEntrando(false)
    }
  }

  const salirAutopack = () => {
    cerrarSesionAutopack()
    setAutopack(null)
  }

  const persona = autorizados.find((a) => String(a.id) === String(firmante))
  const desde = (lista.pagina - 1) * lista.por_pagina
  const ultimaPagina = Math.max(1, Math.ceil(lista.total / lista.por_pagina))

  return (
    <>
      <div className="encabezado">
        <div className="encabezado__marca">
          {/* El robot sale de un original de 1254 px reducido a la medida justa: el
              navegador elige 1x, 2x o 3x según la pantalla y se ve nítido en todas. */}
          <img
            src={robot1x} srcSet={`${robot1x} 1x, ${robot2x} 2x, ${robot3x} 3x`}
            width={96} height={96} alt="" className="encabezado__robot"
          />
          <div>
            <div className="hero__eyebrow">Neostar · Compras</div>
            <h1 className="encabezado__titulo">Autorizaciones de <span>compra</span></h1>
          </div>
        </div>
        <button className="btn btn--primary" onClick={() => navigate('/nueva')}>
          + Nueva solicitud
        </button>
      </div>

      {/* Autorizadas sin aviso a la cajera: no debería aparecer nunca; si aparece, que se vea. */}
      {sinAviso.length > 0 && (
        <div className="alert alert--warning sin-aviso">
          <strong>
            ⚠ {sinAviso.length === 1
              ? 'Una solicitud autorizada no le avisó'
              : `${sinAviso.length} solicitudes autorizadas no le avisaron`} a la cajera.
          </strong>{' '}
          Administración puede mandar el aviso desde acá.
          <div className="sin-aviso__lista">
            {sinAviso.map((s) => (
              <div key={s.id} className="sin-aviso__item">
                <Link to={`/solicitudes/${s.id}`} className="sin-aviso__id">#{s.id}</Link>
                <span className="sin-aviso__prov">{s.proveedor_nombre || 'sin proveedor'}</span>
                <span>{fmtImporte(s.monto_total, s.moneda)}</span>
                <span className="espera">firmada {fmtFechaHora(s.firmada)}</span>
                <button
                  type="button" className="btn btn--ghost btn--sm"
                  disabled={avisando !== null} onClick={() => mandarAviso(s)}
                >
                  {avisando === s.id
                    ? <><span className="spinner spinner--dark" /> Avisando…</>
                    : 'Avisar a la cajera'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
      {resultadoAviso && (
        <div className={`alert alert--${resultadoAviso.tipo === 'error' ? 'error' : 'ok'}`}>
          {resultadoAviso.texto}
        </div>
      )}

      {/* Acceso rápido del firmante */}
      <div className="card firmante-card">
        <div className="firmante-card__top">
          <div className="card__title" style={{ marginBottom: 0 }}>✍️ Para firmar</div>
          <label className="firmante-select">
            Soy:
            <select value={firmante} onChange={(e) => elegirFirmante(e.target.value)}>
              <option value="">Elegí tu nombre…</option>
              {autorizados.map((a) => (
                <option key={a.id} value={a.id}>{a.nombre} · {LISTAS[a.lista] || a.lista}</option>
              ))}
            </select>
          </label>
        </div>

        {firmante && (
          misFirmas.length === 0 ? (
            <div className="card__hint" style={{ marginBottom: 0 }}>
              No tenés solicitudes pendientes para firmar. 🎉
            </div>
          ) : (
            <>
              <div className="firmante-card__top" style={{ marginTop: '0.6rem' }}>
                <div className="card__hint" style={{ marginBottom: 0 }}>
                  Tenés <strong>{misFirmas.length}</strong> para firmar:
                </div>
                {misFirmas.length > 1 && !firmandoLote && persona && (
                  <button className="btn btn--primary btn--sm"
                          onClick={() => { setFirmandoLote(true); setAvisoLote('') }}>
                    ✍️ Firmar las {misFirmas.length}
                  </button>
                )}
              </div>
              <div className="para-firmar-lista">
                {misFirmas.map((s) => (
                  <button
                    key={s.id} className="para-firmar-item"
                    onClick={() => navigate(`/solicitudes/${s.id}`)}
                  >
                    <span className="para-firmar-item__id">#{s.id}</span>
                    <span className="para-firmar-item__prov">
                      {s.proveedor_nombre}
                      <span className="para-firmar-item__marca">
                        {' · '}{(s.marcas || []).length > 1 ? 'varias marcas' : (s.marca === 'OTRO' ? s.marca_otro : s.marca)}
                      </span>
                    </span>
                    {s.criticidad === 'urgente' && (
                      <span className="badge badge--danger">Urgente</span>
                    )}
                    {(() => {
                      const e = esperaDesde(s.created_at)
                      return <span className={`espera ${e.demorada ? 'espera--demorada' : ''}`}>{e.texto}</span>
                    })()}
                    <span className="para-firmar-item__monto">{fmtImporte(s.monto_total, s.moneda)}</span>
                    {s.requiere_segunda_firma && (
                      <span className="badge badge--warning">falta 2ª firma</span>
                    )}
                  </button>
                ))}
              </div>
              {firmandoLote && persona && (
                <PanelLote
                  solicitudes={misFirmas} persona={persona}
                  onCancelar={() => setFirmandoLote(false)}
                  onListo={(res) => {
                    setAvisoLote(res.resumen)
                    if (!(res.salteadas || []).length) setFirmandoLote(false)
                    cargar()
                  }}
                />
              )}
            </>
          )
        )}
        {avisoLote && <div className="alert alert--ok" style={{ marginTop: '0.9rem', marginBottom: 0 }}>{avisoLote}</div>}
      </div>

      <div className="card">
        <div className="toolbar">
          <input
            type="text" className="filtro filtro--busqueda" placeholder="Buscar proveedor, CUIT, factura, quién la pidió…"
            value={filtros.q} onChange={(e) => filtrar('q', e.target.value)}
          />
          <a className="btn btn--ghost btn--sm" href={urlExcel(consulta)}
             title="Todas las solicitudes que cumplen los filtros, en una planilla de Excel">
            ⬇ Exportar a Excel
          </a>
        </div>
        <div className="filtros">
          <select className="filtro" value={filtros.estado} onChange={(e) => filtrar('estado', e.target.value)}>
            <option value="">Todos los estados</option>
            <option value="pendiente">Pendientes</option>
            <option value="autorizada">Autorizadas</option>
            <option value="observada">Observadas (devueltas)</option>
            <option value="rechazada">Rechazadas</option>
          </select>
          <select className="filtro" value={filtros.empresa} onChange={(e) => filtrar('empresa', e.target.value)}>
            <option value="">Todas las razones sociales</option>
            {EMPRESAS.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
          <select className="filtro" value={filtros.marca} onChange={(e) => filtrar('marca', e.target.value)}>
            <option value="">Todas las marcas</option>
            {MARCAS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <select className="filtro" value={filtros.ubicacion} onChange={(e) => filtrar('ubicacion', e.target.value)}>
            <option value="">Rosario y Santa Fe</option>
            {UBICACIONES.map((u) => <option key={u.valor} value={u.valor}>{u.etiqueta}</option>)}
          </select>
          <label className="filtro filtro--check">
            <input type="checkbox" checked={filtros.urgente} onChange={(e) => filtrar('urgente', e.target.checked)} />
            Solo urgentes
          </label>
          <label className="filtro filtro--fechas">
            Cargadas del
            <input type="date" value={filtros.desde} onChange={(e) => filtrar('desde', e.target.value)} />
            al
            <input type="date" value={filtros.hasta} onChange={(e) => filtrar('hasta', e.target.value)} />
          </label>
          {hayFiltros && (
            <button type="button" className="btn-link" onClick={() => { setFiltros(SIN_FILTROS); setPagina(1) }}>
              Limpiar filtros
            </button>
          )}
        </div>

        {mensaje && (
          <div className={`alert alert--${mensaje.tipo === 'error' ? 'error' : 'ok'}`}>
            {mensaje.texto}
          </div>
        )}

        {seleccion.length > 0 && (
          <div className="barra-seleccion">
            <span><strong>{seleccion.length}</strong> seleccionada(s)</span>
            <div className="toolbar__actions">
              <a className="btn btn--ghost btn--sm" href={urlZipLote(seleccion)}>
                ⬇ Descargar ZIP
              </a>
              <button className="btn btn--ghost btn--sm" onClick={() => setSeleccion([])}>
                Limpiar
              </button>
            </div>
          </div>
        )}

        {cargando && solicitudes.length === 0 ? (
          <div className="empty"><span className="spinner spinner--dark" /> Cargando…</div>
        ) : solicitudes.length === 0 ? (
          <div className="empty">
            <div className="empty__icon">📄</div>
            {hayFiltros ? (
              <p>Ninguna solicitud cumple estos filtros.</p>
            ) : (
              <>
                <p>No hay solicitudes todavía.</p>
                <p style={{ marginTop: '0.6rem' }}>
                  <Link to="/nueva">Subí una factura</Link> para empezar.
                </p>
              </>
            )}
          </div>
        ) : (
          <div className="table-wrap" style={{ opacity: cargando ? 0.6 : 1 }}>
            <table className="data">
              <thead>
                <tr>
                  <th style={{ width: 34 }}>
                    <input type="checkbox" checked={todasElegidas} onChange={alternarTodas}
                           title="Elegir todas las de esta página" />
                  </th>
                  <th>#</th>
                  <th title="Cuándo se cargó en la app: es la fecha que usa el filtro">Cargada</th>
                  <th>Proveedor</th>
                  <th>Marca</th>
                  <th className="num">Monto</th>
                  <th>Firmante</th>
                  <th>Estado</th>
                  <th title="Cargado en Autopack">Autopack</th>
                </tr>
              </thead>
              <tbody>
                {solicitudes.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => navigate(`/solicitudes/${s.id}`)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={seleccion.includes(s.id)}
                        onChange={() => alternar(s.id)}
                      />
                    </td>
                    <td><strong>{s.id}</strong></td>
                    {/* La fecha de carga es la que filtra "Cargadas del … al …"; la de la
                        factura va debajo para no confundirlas. */}
                    <td title={fmtFechaHora(s.created_at)}>
                      {fmtFechaHora(s.created_at).slice(0, 10)}
                      {s.fecha && <div className="espera">Factura {s.fecha}</div>}
                    </td>
                    <td>
                      {s.proveedor_nombre}
                      <div className="espera">
                        {s.facturas > 1 ? `${s.facturas} facturas` : s.factura_numero
                          ? `Factura ${s.factura_numero}` : ''}
                        {s.criticidad === 'urgente' && (
                          <span className="badge badge--danger" style={{ marginLeft: '0.4rem' }}>Urgente</span>
                        )}
                      </div>
                    </td>
                    <td>
                      {s.marca === 'OTRO' ? s.marca_otro || 'Otro' : s.marca}
                      {(() => {
                        let n = 0
                        try { n = JSON.parse(s.marcas || '[]').length } catch { n = 0 }
                        return n > 1 ? <span className="espera"> +{n - 1}</span> : null
                      })()}
                    </td>
                    <td className="num">{fmtImporte(s.monto_total, s.moneda)}</td>
                    <td>
                      {s.estado === 'autorizada' ? (
                        <span style={{ fontSize: '0.85rem' }}>✓ {s.firmado_por || '—'}</span>
                      ) : s.estado === 'observada' || s.estado === 'rechazada' ? (
                        // Quién la devolvió o rechazó y por qué (completo al pasar el mouse).
                        <>
                          <span style={{ fontSize: '0.85rem' }}>
                            {s.estado === 'rechazada' ? '✕ Rechazó' : '↩ Devolvió'} {s.revision_por || '—'}
                          </span>
                          <div className="espera" title={s.revision_motivo}>
                            «{(s.revision_motivo || '').length > 60
                              ? `${s.revision_motivo.slice(0, 57)}…` : s.revision_motivo}»
                          </div>
                        </>
                      ) : (() => {
                        // A quién espera y desde cuándo: el que la frena tiene nombre.
                        const e = esperaDesde(s.created_at)
                        return (
                          <>
                            {s.firmante || <span style={{ color: 'var(--text-muted)' }}>Cualquier habilitado</span>}
                            <div className={`espera ${e.demorada ? 'espera--demorada' : ''}`}>esperando {e.texto}</div>
                          </>
                        )
                      })()}
                    </td>
                    <td>
                      <span className={`badge badge--${estadoDe(s.estado).badge}`}>{estadoDe(s.estado).etiqueta}</span>
                    </td>
                    <td onClick={(e) => autopack && e.stopPropagation()} style={{ textAlign: 'center' }}
                        title={s.autopack_ok && s.autopack_por
                          ? `Cargado en Autopack: lo marcó ${s.autopack_por} el ${fmtFechaHora(s.autopack_fecha)}`
                          : 'Todavía no se cargó en Autopack'}>
                      {autopack ? (
                        <input
                          type="checkbox" checked={!!s.autopack_ok}
                          onChange={(e) => guardarAutopack(s, e.target.checked)}
                        />
                      ) : s.autopack_ok
                        ? <span className="autopack-si">✓</span>
                        : <span className="autopack-no">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {lista.total > 0 && (
          <div className="paginacion">
            <span className="toolbar__info">
              {lista.total <= lista.por_pagina
                ? `${lista.total} ${lista.total === 1 ? 'solicitud' : 'solicitudes'}`
                : `Mostrando ${desde + 1}–${desde + solicitudes.length} de ${lista.total}`}
              {hayFiltros && ' con estos filtros'}
            </span>
            {ultimaPagina > 1 && (
              <div className="toolbar__actions">
                <button className="btn btn--ghost btn--sm" disabled={pagina <= 1}
                        onClick={() => setPagina((p) => p - 1)}>‹ Anterior</button>
                <span className="toolbar__info">Página {lista.pagina} de {ultimaPagina}</span>
                <button className="btn btn--ghost btn--sm" disabled={pagina >= ultimaPagina}
                        onClick={() => setPagina((p) => p + 1)}>Siguiente ›</button>
              </div>
            )}
          </div>
        )}

        <div className="field__nota" style={{ marginTop: '0.9rem' }}>
          La columna <strong>Autopack</strong> la marca administración cuando la operación ya se
          cargó en el otro sistema.{' '}
          {autopack ? (
            <>Marcando como <strong>{autopack.nombre}</strong> ·{' '}
              <button type="button" className="btn-link" onClick={salirAutopack}>Salir</button>
            </>
          ) : (
            <button type="button" className="btn-link"
                    onClick={() => { setApError(''); setLoginAutopack({}) }}>
              Soy de administración: marcar Autopack
            </button>
          )}
        </div>
      </div>

      {loginAutopack && (
        <div className="modal-fondo" onClick={() => !apEntrando && setLoginAutopack(null)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={entrarAutopack}>
            <div className="card__title" style={{ marginBottom: '0.3rem' }}>
              {loginAutopack.avisar ? 'Avisar a la cajera' : 'Autopack'}
            </div>
            <p className="card__hint">
              {loginAutopack.avisar
                ? `Mandar el aviso de la #${loginAutopack.avisar.id} lo hace solo administración. `
                  + 'Ingresá tu mail y la clave de Autopack'
                : 'Solo administración puede marcar Autopack. Ingresá tu mail y la clave'}
              : se te pide una sola vez mientras tengas abierta esta pestaña.
            </p>
            {apError && <div className="alert alert--error">{apError}</div>}
            <div className="field">
              <label>Mail</label>
              <input
                type="email" autoFocus value={apEmail} onChange={(e) => setApEmail(e.target.value)}
                placeholder="usuario@neostar.com.ar" autoComplete="username"
              />
            </div>
            <div className="field">
              <label>Clave</label>
              <input
                type="password" value={apClave} onChange={(e) => setApClave(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <div className="toolbar" style={{ marginBottom: 0, marginTop: '0.6rem' }}>
              <button type="button" className="btn btn--ghost" onClick={() => setLoginAutopack(null)}
                      disabled={apEntrando}>
                Cancelar
              </button>
              <button type="submit" className="btn btn--primary"
                      disabled={apEntrando || !apEmail.trim() || !apClave}>
                {apEntrando ? <><span className="spinner" /> Verificando…</> : 'Ingresar'}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  )
}
