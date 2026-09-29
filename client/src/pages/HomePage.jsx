import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PanelLote from '../components/PanelLote.jsx'
import robot from '../assets/robot-id.png'
import { LISTAS, fmtFechaHora, fmtMoney } from '../constants.js'
import {
  cerrarSesionAutopack, iniciarSesionAutopack, listarAutorizados, listarSolicitudes,
  marcarAutopack, paraFirmar, sesionAutopack, urlZipLote,
} from '../services/api.js'

export default function HomePage() {
  const navigate = useNavigate()
  const [solicitudes, setSolicitudes] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [estado, setEstado] = useState('')
  const [cargando, setCargando] = useState(true)
  const [seleccion, setSeleccion] = useState([])
  const [mensaje, setMensaje] = useState(null)

  // Acceso rápido del firmante (sin login): elige su nombre, el navegador lo recuerda.
  const [autorizados, setAutorizados] = useState([])
  const [firmante, setFirmante] = useState(() => localStorage.getItem('firmante') || '')
  const [misFirmas, setMisFirmas] = useState([])

  useEffect(() => { listarAutorizados().then(setAutorizados).catch(() => {}) }, [])

  const cargarMisFirmas = useCallback(async (id) => {
    if (!id) { setMisFirmas([]); return }
    try {
      setMisFirmas(await paraFirmar(id))
    } catch {
      setMisFirmas([])
    }
  }, [])

  useEffect(() => { cargarMisFirmas(firmante) }, [firmante, cargarMisFirmas, solicitudes])

  const elegirFirmante = (id) => {
    setFirmante(id)
    if (id) localStorage.setItem('firmante', id)
    else localStorage.removeItem('firmante')
  }

  const cargar = useCallback(async () => {
    setCargando(true)
    try {
      setSolicitudes(await listarSolicitudes({ q: busqueda, estado }))
    } finally {
      setCargando(false)
    }
  }, [busqueda, estado])

  useEffect(() => {
    const t = setTimeout(cargar, 250)
    return () => clearTimeout(t)
  }, [cargar])

  const alternar = (id) =>
    setSeleccion((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  const alternarTodas = () =>
    setSeleccion((s) => (s.length === solicitudes.length ? [] : solicitudes.map((x) => x.id)))

  // Autopack lo tilda solo administración: mail + clave, pedidos una vez por pestaña.
  const [autopack, setAutopack] = useState(sesionAutopack)
  const [loginAutopack, setLoginAutopack] = useState(null)   // { s, valor } que espera el login
  const [apEmail, setApEmail] = useState('')
  const [apClave, setApClave] = useState('')
  const [apError, setApError] = useState('')
  const [apEntrando, setApEntrando] = useState(false)

  // El tilde se guarda al instante; se refleja localmente para no recargar todo.
  const guardarAutopack = async (s, valor) => {
    setSolicitudes((lista) =>
      lista.map((x) => (x.id === s.id ? { ...x, autopack_ok: valor ? 1 : 0 } : x)))
    try {
      const r = await marcarAutopack(s.id, valor)
      setSolicitudes((lista) => lista.map((x) => (x.id === s.id
        ? { ...x, autopack_por: r.autopack_por, autopack_fecha: r.autopack_fecha } : x)))
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

  const cambiarAutopack = (s, valor) => {
    if (autopack) guardarAutopack(s, valor)
    else {
      setApError('')
      setLoginAutopack({ s, valor })
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
      if (pendiente) guardarAutopack(pendiente.s, pendiente.valor)
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

  const elegidas = solicitudes.filter((s) => seleccion.includes(s.id))
  const pendientesElegidas = elegidas.filter((s) => s.estado !== 'autorizada')

  return (
    <>
      <div className="hero">
        <div className="hero__text">
          <div className="hero__eyebrow">Neostar · Compras</div>
          <h1 className="hero__title">Autorizaciones de <span>compra</span></h1>
          <p className="hero__subtitle">
            Subí la factura del proveedor, revisá los datos y hacé que dos autorizados
            firmen. El formulario F 8.4-01 se completa solo.
          </p>
        </div>
        <img src={robot} alt="" className="hero__robot" />
      </div>

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
              <div className="card__hint">
                Tenés <strong>{misFirmas.length}</strong> para firmar:
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
                    <span className="para-firmar-item__monto">$ {fmtMoney(s.monto_total)}</span>
                    {s.requiere_segunda_firma && (
                      <span className="badge badge--warning">falta 2ª firma</span>
                    )}
                  </button>
                ))}
              </div>
            </>
          )
        )}
      </div>

      <div className="card">
        <div className="toolbar">
          <div className="toolbar__actions">
            <input
              type="text" className="cell-input" placeholder="Buscar proveedor, CUIT, marca…"
              value={busqueda} onChange={(e) => setBusqueda(e.target.value)}
              style={{ border: '1px solid var(--border-strong)', minWidth: 260, padding: '0.5rem 0.7rem' }}
            />
            <select
              value={estado} onChange={(e) => setEstado(e.target.value)}
              style={{
                padding: '0.5rem 0.7rem', borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-strong)', fontFamily: 'inherit',
              }}
            >
              <option value="">Todas</option>
              <option value="pendiente">Pendientes</option>
              <option value="autorizada">Autorizadas</option>
            </select>
          </div>
          <button className="btn btn--primary" onClick={() => navigate('/nueva')}>
            + Nueva solicitud
          </button>
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

        {pendientesElegidas.length > 0 && (
          <PanelLote
            solicitudes={pendientesElegidas}
            onListo={(res) => {
              setMensaje({ tipo: 'ok', texto: res.resumen })
              setSeleccion([])
              cargar()
            }}
          />
        )}

        {cargando ? (
          <div className="empty"><span className="spinner spinner--dark" /> Cargando…</div>
        ) : solicitudes.length === 0 ? (
          <div className="empty">
            <div className="empty__icon">📄</div>
            <p>No hay solicitudes todavía.</p>
            <p style={{ marginTop: '0.6rem' }}>
              <Link to="/nueva">Subí una factura</Link> para empezar.
            </p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th style={{ width: 34 }}>
                    <input
                      type="checkbox"
                      checked={seleccion.length === solicitudes.length && solicitudes.length > 0}
                      onChange={alternarTodas}
                    />
                  </th>
                  <th>#</th>
                  <th>Fecha</th>
                  <th>Proveedor</th>
                  <th>Marca</th>
                  <th className="num">Monto</th>
                  <th>Firmas</th>
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
                    <td>{s.fecha}</td>
                    <td>
                      {s.proveedor_nombre}
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
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
                        return n > 1 ? <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}> +{n - 1}</span> : null
                      })()}
                    </td>
                    <td className="num">$ {fmtMoney(s.monto_total)}</td>
                    <td>
                      <span className={`badge ${s.estado === 'autorizada' ? 'badge--success' : 'badge--muted'}`}>
                        {s.firmas} {s.firmas === 1 ? 'firma' : 'firmas'}
                      </span>
                    </td>
                    <td>
                      {s.estado === 'autorizada'
                        ? <span className="badge badge--success">Autorizada</span>
                        : <span className="badge badge--warning">Pendiente</span>}
                    </td>
                    <td onClick={(e) => e.stopPropagation()} style={{ textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={!!s.autopack_ok}
                        onChange={(e) => cambiarAutopack(s, e.target.checked)}
                        title={s.autopack_ok && s.autopack_por
                          ? `Tildado por ${s.autopack_por} el ${fmtFechaHora(s.autopack_fecha)}`
                          : 'Marcar cuando la operación ya se cargó en Autopack (solo administración)'}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="field__nota" style={{ marginTop: '0.9rem' }}>
          La columna <strong>Autopack</strong> es el control de administración: se tilda cuando la
          operación ya se cargó en el otro sistema. Solo la puede tildar administración, con su mail
          y la clave.
          {autopack && (
            <>{' '}Autopack: <strong>{autopack.nombre}</strong> ·{' '}
              <button type="button" className="btn btn--ghost btn--sm" onClick={salirAutopack}>
                Salir
              </button>
            </>
          )}
        </div>
      </div>

      {loginAutopack && (
        <div className="modal-fondo" onClick={() => !apEntrando && setLoginAutopack(null)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={entrarAutopack}>
            <div className="card__title" style={{ marginBottom: '0.3rem' }}>Autopack</div>
            <p className="card__hint">
              Solo administración puede {loginAutopack.valor ? 'tildar' : 'destildar'} Autopack.
              Ingresá tu mail y la clave: se te pide una sola vez mientras tengas abierta esta pestaña.
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
