import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import robot from '../assets/robot-id.png'
import { fmtMoney } from '../constants.js'
import { listarSolicitudes } from '../services/api.js'

export default function HomePage() {
  const navigate = useNavigate()
  const [solicitudes, setSolicitudes] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [estado, setEstado] = useState('')
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    const t = setTimeout(async () => {
      setCargando(true)
      try {
        setSolicitudes(await listarSolicitudes({ q: busqueda, estado }))
      } finally {
        setCargando(false)
      }
    }, 250)
    return () => clearTimeout(t)
  }, [busqueda, estado])

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
                  <th>#</th>
                  <th>Fecha</th>
                  <th>Proveedor</th>
                  <th>Marca</th>
                  <th>Empresa</th>
                  <th className="num">Monto</th>
                  <th>Firmas</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {solicitudes.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => navigate(`/solicitudes/${s.id}`)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td><strong>{s.id}</strong></td>
                    <td>{s.fecha}</td>
                    <td>
                      {s.proveedor_nombre}
                      {s.factura_numero && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Factura {s.factura_numero}
                        </div>
                      )}
                    </td>
                    <td>{s.marca === 'OTRO' ? s.marca_otro || 'Otro' : s.marca}</td>
                    <td style={{ fontSize: '0.8rem' }}>{s.empresa}</td>
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
