import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PanelLote from '../components/PanelLote.jsx'
import robot from '../assets/robot-id.png'
import { fmtMoney } from '../constants.js'
import { listarSolicitudes, marcarAutopack, urlZipLote } from '../services/api.js'

export default function HomePage() {
  const navigate = useNavigate()
  const [solicitudes, setSolicitudes] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [estado, setEstado] = useState('')
  const [cargando, setCargando] = useState(true)
  const [seleccion, setSeleccion] = useState([])
  const [mensaje, setMensaje] = useState(null)

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
                    <td>{s.marca === 'OTRO' ? s.marca_otro || 'Otro' : s.marca}</td>
                    <td className="num">$ {fmtMoney(s.monto_total)}</td>
                    <td>
                      <span className={`badge ${s.firmas >= 2 ? 'badge--success' : 'badge--muted'}`}>
                        {s.firmas}/2
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
