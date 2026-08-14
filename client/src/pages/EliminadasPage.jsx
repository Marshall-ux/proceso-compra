import { useEffect, useState } from 'react'
import { fmtFechaHora, fmtMoney } from '../constants.js'
import { listarEliminaciones } from '../services/api.js'

// Historial de solicitudes eliminadas: qué se borró, por qué, quién y cuándo.
export default function EliminadasPage() {
  const [registros, setRegistros] = useState([])
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    listarEliminaciones().then(setRegistros).finally(() => setCargando(false))
  }, [])

  return (
    <>
      <div className="hero" style={{ marginBottom: '1.6rem' }}>
        <div className="hero__text">
          <div className="hero__eyebrow">Auditoría</div>
          <h1 className="hero__title" style={{ fontSize: '2.2rem' }}>Solicitudes eliminadas</h1>
          <p className="hero__subtitle">
            Registro de todo lo que se borró: qué solicitud, por qué motivo, quién la eliminó y cuándo.
          </p>
        </div>
      </div>

      <div className="card">
        {cargando ? (
          <div className="empty"><span className="spinner spinner--dark" /> Cargando…</div>
        ) : registros.length === 0 ? (
          <div className="empty">
            <div className="empty__icon">🗑️</div>
            <p>No se eliminó ninguna solicitud todavía.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Solicitud</th>
                  <th>Proveedor</th>
                  <th>Marca</th>
                  <th className="num">Monto</th>
                  <th>Estado al borrar</th>
                  <th>Motivo</th>
                  <th>Eliminó</th>
                  <th>Fecha</th>
                </tr>
              </thead>
              <tbody>
                {registros.map((r) => (
                  <tr key={r.id}>
                    <td><strong>#{r.solicitud_id}</strong></td>
                    <td>
                      {r.proveedor_nombre}
                      {r.factura_numero && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Factura {r.factura_numero}
                        </div>
                      )}
                    </td>
                    <td>{r.marca}</td>
                    <td className="num">$ {fmtMoney(r.monto_total)}</td>
                    <td>
                      {r.estado === 'autorizada'
                        ? <span className="badge badge--success">Autorizada · {r.firmas}/2</span>
                        : <span className="badge badge--warning">Pendiente · {r.firmas}/2</span>}
                    </td>
                    <td style={{ maxWidth: 280 }}>{r.motivo}</td>
                    <td>{r.eliminado_por || <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                    <td style={{ whiteSpace: 'nowrap', fontSize: '0.85rem' }}>{fmtFechaHora(r.fecha)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="field__nota" style={{ marginTop: '0.9rem' }}>
          Este registro es solo de lectura: queda como constancia. Las solicitudes eliminadas no se
          pueden restaurar.
        </div>
      </div>
    </>
  )
}
