import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PanelLote from '../components/PanelLote.jsx'
import robot from '../assets/robot-id.png'
import { LISTAS, fmtMoney } from '../constants.js'
import {
  listarAutorizados, listarSolicitudes, marcarAutopack, paraFirmar, urlZipLote,
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

  // El tilde de Autopack se guarda al instante; se refleja localmente para no recargar todo.
  const cambiarAutopack = async (s, valor) => {
    setSolicitudes((lista) =>
      lista.map((x) => (x.id === s.id ? { ...x, autopack_ok: valor ? 1 : 0 } : x)))
    try {
      await marcarAutopack(s.id, valor)
    } catch (e) {
      setMensaje({ tipo: 'error', texto: e.message })
      cargar()
    }
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
                        title="Marcar cuando la operación ya se cargó en Autopack"
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
          operación ya se cargó en el otro sistema.
        </div>
      </div>
    </>
  )
}
