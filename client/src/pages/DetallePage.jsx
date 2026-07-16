import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import FormularioSolicitud from '../components/FormularioSolicitud.jsx'
import PanelAutorizacion from '../components/PanelAutorizacion.jsx'
import { fmtMoney } from '../constants.js'
import {
  actualizarSolicitud, eliminarSolicitud, obtenerSolicitud, urlFactura, urlPdf,
} from '../services/api.js'

export default function DetallePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [solicitud, setSolicitud] = useState(null)
  const [borrador, setBorrador] = useState(null)
  const [editando, setEditando] = useState(false)
  const [error, setError] = useState('')
  const [errores, setErrores] = useState([])
  const [guardando, setGuardando] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setSolicitud(await obtenerSolicitud(id))
    } catch (e) {
      setError(e.message)
    }
  }, [id])

  useEffect(() => { cargar() }, [cargar])

  if (error) return <div className="alert alert--error">{error}</div>
  if (!solicitud) return <div className="empty"><span className="spinner spinner--dark" /> Cargando…</div>

  const completa = solicitud.estado === 'autorizada'

  const empezarEdicion = () => {
    setBorrador({ ...solicitud })
    setEditando(true)
    setErrores([])
  }

  const guardar = async () => {
    setGuardando(true)
    setErrores([])
    try {
      const r = await actualizarSolicitud(id, borrador)
      setSolicitud({ ...r, autorizados_disponibles: solicitud.autorizados_disponibles })
      setEditando(false)
      await cargar()
    } catch (e) {
      setErrores(e.data?.errores || [e.message])
    } finally {
      setGuardando(false)
    }
  }

  const borrar = async () => {
    if (!confirm('¿Eliminar esta solicitud? No se puede deshacer.')) return
    await eliminarSolicitud(id)
    navigate('/')
  }

  return (
    <>
      <div className="toolbar">
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 800 }}>
            Solicitud #{solicitud.id}{' '}
            {completa
              ? <span className="badge badge--success">Autorizada</span>
              : <span className="badge badge--warning">Pendiente · {solicitud.autorizaciones.length}/2 firmas</span>}
          </h1>
          <div className="toolbar__info">
            {solicitud.proveedor_nombre} · {solicitud.marca} · $ {fmtMoney(solicitud.monto_total)}
            {solicitud.factura_archivo && (
              <> · <a className="link-factura" href={urlFactura(solicitud.id)} target="_blank" rel="noreferrer">
                ver factura original
              </a></>
            )}
          </div>
        </div>
        <div className="toolbar__actions">
          <button className="btn btn--ghost" onClick={() => navigate('/')}>← Solicitudes</button>
          <a className="btn btn--ghost" href={urlPdf(solicitud.id)} target="_blank" rel="noreferrer">
            Ver PDF
          </a>
          <a className="btn btn--primary" href={urlPdf(solicitud.id)} download>Descargar</a>
        </div>
      </div>

      <PanelAutorizacion solicitud={solicitud} onActualizar={setSolicitud} />

      <div className="card">
        <div className="toolbar" style={{ marginBottom: editando ? '1.2rem' : 0 }}>
          <div className="card__title" style={{ marginBottom: 0 }}>📋 Datos de la autorización</div>
          {!completa && !editando && (
            <div className="toolbar__actions">
              <button className="btn btn--ghost btn--sm" onClick={empezarEdicion}>Editar</button>
              <button className="btn btn--danger btn--sm" onClick={borrar}>Eliminar</button>
            </div>
          )}
        </div>

        {editando ? (
          <>
            {solicitud.autorizaciones.length > 0 && (
              <div className="alert alert--warning">
                Esta solicitud ya tiene {solicitud.autorizaciones.length} firma(s). Si guardás cambios,
                se borran y hay que volver a autorizar: nadie firma algo que después se modificó.
              </div>
            )}
            {errores.length > 0 && (
              <div className="alert alert--error">
                Revisá estos puntos:
                <ul>{errores.map((e, i) => <li key={i}>{e}</li>)}</ul>
              </div>
            )}
            <FormularioSolicitud datos={borrador} onChange={setBorrador} />
            <div className="toolbar" style={{ marginBottom: 0 }}>
              <button className="btn btn--ghost" onClick={() => setEditando(false)}>Cancelar</button>
              <button className="btn btn--primary" onClick={guardar} disabled={guardando}>
                {guardando ? <><span className="spinner" /> Guardando…</> : 'Guardar cambios'}
              </button>
            </div>
          </>
        ) : (
          <iframe className="visor" src={urlPdf(solicitud.id)} title={`Autorización ${solicitud.id}`} />
        )}
      </div>
    </>
  )
}
