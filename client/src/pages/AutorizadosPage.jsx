import { useEffect, useState } from 'react'
import { LISTAS, fmtMoney } from '../constants.js'
import { blanquearPin, listarAutorizados } from '../services/api.js'

// Consulta de las 4 planillas de autorizados (Nissan, Jeep, Kia, Multimarca).
export default function AutorizadosPage() {
  const [autorizados, setAutorizados] = useState([])
  const [lista, setLista] = useState('')
  const [cargando, setCargando] = useState(true)

  const cargar = () => {
    setCargando(true)
    listarAutorizados(lista).then(setAutorizados).finally(() => setCargando(false))
  }

  useEffect(cargar, [lista])

  const blanquear = async (a) => {
    if (!confirm(`¿Blanquear el PIN de ${a.nombre}? Va a tener que definir uno nuevo la próxima vez que firme.`)) return
    await blanquearPin(a.id)
    cargar()
  }

  return (
    <>
      <div className="hero" style={{ marginBottom: '1.6rem' }}>
        <div className="hero__text">
          <div className="hero__eyebrow">Referencia</div>
          <h1 className="hero__title" style={{ fontSize: '2.2rem' }}>Autorizados</h1>
          <p className="hero__subtitle">
            Quién puede autorizar cada compra y hasta qué monto, según las planillas firmadas por dirección.
          </p>
        </div>
      </div>

      <div className="card">
        <div className="toolbar">
          <div className="opciones">
            <label className={`opcion ${lista === '' ? 'opcion--activa' : ''}`}>
              <input type="radio" name="lista" checked={lista === ''} onChange={() => setLista('')} />
              Todas
            </label>
            {Object.entries(LISTAS).map(([k, v]) => (
              <label key={k} className={`opcion ${lista === k ? 'opcion--activa' : ''}`}>
                <input type="radio" name="lista" checked={lista === k} onChange={() => setLista(k)} />
                {v}
              </label>
            ))}
          </div>
          <span className="toolbar__info">{autorizados.length} personas</span>
        </div>

        {cargando ? (
          <div className="empty"><span className="spinner spinner--dark" /> Cargando…</div>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Colaborador</th>
                  <th>Cargo</th>
                  <th>Planilla</th>
                  <th className="num">Monto autorizado</th>
                  <th>Conceptos</th>
                  <th>PIN</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {autorizados.map((a) => (
                  <tr key={a.id}>
                    <td><strong>{a.nombre}</strong></td>
                    <td style={{ fontSize: '0.82rem' }}>{a.cargo}</td>
                    <td><span className="badge badge--muted">{LISTAS[a.lista] || a.lista}</span></td>
                    <td className="num">
                      {a.sin_limite
                        ? <span className="badge badge--info">Sin límite</span>
                        : <>$ {fmtMoney(a.monto_autorizado)}</>}
                    </td>
                    <td style={{ fontSize: '0.78rem', color: 'var(--text-soft)', maxWidth: 340 }}>
                      {a.conceptos}
                    </td>
                    <td>
                      {a.tiene_pin
                        ? <span className="badge badge--success">Activo</span>
                        : <span className="badge badge--muted">Sin definir</span>}
                    </td>
                    <td>
                      {a.tiene_pin && (
                        <button className="btn btn--danger btn--sm" onClick={() => blanquear(a)}>
                          Blanquear PIN
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="field__nota" style={{ marginTop: '0.9rem' }}>
          Los autorizados de <strong>Multimarca</strong> pueden autorizar cualquier marca.
          La planilla de Kia cubre también Suzuki, y la de Jeep corresponde a FCA / Chrysler.
        </div>
      </div>
    </>
  )
}
