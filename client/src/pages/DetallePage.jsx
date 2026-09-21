import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import FormularioSolicitud from '../components/FormularioSolicitud.jsx'
import PanelAutorizacion from '../components/PanelAutorizacion.jsx'
import SeccionPagos from '../components/SeccionPagos.jsx'
import { fmtMoney } from '../constants.js'
import {
  actualizarSolicitud, eliminarSolicitud, obtenerSolicitud,
  urlCbuImagen, urlFactura, urlLegajo, urlPdf, urlPdfCompleto, urlZip,
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
  const [borrando, setBorrando] = useState(false)      // muestra el modal de motivo
  const [motivo, setMotivo] = useState('')
  const [eliminadoPor, setEliminadoPor] = useState('')
  const [claveBorrar, setClaveBorrar] = useState('')   // clave admin (solo autorizadas)
  const [errorBorrar, setErrorBorrar] = useState('')
  const [confirmando, setConfirmando] = useState(false)

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

  const confirmarBorrado = async () => {
    setErrorBorrar('')
    if (!motivo.trim()) {
      setErrorBorrar('El motivo es obligatorio: dejá registrado por qué se elimina.')
      return
    }
    // Una solicitud ya autorizada solo la puede eliminar administración con la clave.
    if (completa && !claveBorrar.trim()) {
      setErrorBorrar('Está autorizada: ingresá la clave de administración para eliminarla.')
      return
    }
    setConfirmando(true)
    try {
      await eliminarSolicitud(id, { motivo: motivo.trim(), eliminado_por: eliminadoPor.trim() },
                              completa ? claveBorrar.trim() : undefined)
      navigate('/')
    } catch (e) {
      setErrorBorrar(e.message)
    } finally {
      setConfirmando(false)
    }
  }

  return (
    <>
      <div className="toolbar">
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 800 }}>
            Solicitud #{solicitud.id}{' '}
            {completa
              ? <span className="badge badge--success">Autorizada</span>
              : <span className="badge badge--warning">
                  {solicitud.requiere_segunda_firma ? 'Pendiente · falta 2ª firma' : 'Pendiente'}
                </span>}
          </h1>
          <div className="toolbar__info">
            {solicitud.proveedor_nombre} · {solicitud.marca} · $ {fmtMoney(solicitud.monto_total)}
            {solicitud.criticidad === 'urgente' && <> · <span className="badge badge--danger">Urgente</span></>}
            {solicitud.avisados?.length > 0 && <> · 📧 Aviso a {solicitud.avisados.join(', ')}</>}
          </div>
          <div className="toolbar__info" style={{ marginTop: '0.35rem', display: 'flex', gap: '0.9rem', flexWrap: 'wrap' }}>
            {solicitud.facturas?.map((f, i) => (
              <a key={f.id} className="link-factura" href={urlFactura(solicitud.id, f.id)} target="_blank" rel="noreferrer">
                📄 {solicitud.facturas.length > 1 ? `factura ${i + 1}` : 'ver factura'}
              </a>
            ))}
            {solicitud.cbu_imagen && (
              <a className="link-factura" href={urlCbuImagen(solicitud.id)} target="_blank" rel="noreferrer">🏦 CBU (imagen)</a>
            )}
            {solicitud.legajo_archivo && (
              <a className="link-factura" href={urlLegajo(solicitud.id)} target="_blank" rel="noreferrer">📁 legajo impositivo</a>
            )}
          </div>
        </div>
        <div className="toolbar__actions">
          <button className="btn btn--ghost" onClick={() => navigate('/')}>← Solicitudes</button>
          <a className="btn btn--ghost" href={urlPdf(solicitud.id)} target="_blank" rel="noreferrer">
            Ver PDF
          </a>
          {solicitud.facturas?.length > 0 && (
            <a
              className="btn btn--ghost" href={urlPdfCompleto(solicitud.id)}
              target="_blank" rel="noreferrer"
              title="La autorización y las facturas en un solo PDF, para imprimir todo junto"
            >
              🖨 Autorización + facturas
            </a>
          )}
          <a
            className="btn btn--primary" href={urlZip(solicitud.id)}
            title="Todo (autorización, facturas, legajo, CBU y un resumen) para archivar en el disco"
          >
            ⬇ Descargar todo (ZIP)
          </a>
        </div>
      </div>

      <PanelAutorizacion solicitud={solicitud} onActualizar={setSolicitud} />

      {completa && <SeccionPagos solicitud={solicitud} onActualizar={setSolicitud} />}

      <div className="card">
        <div className="toolbar" style={{ marginBottom: editando ? '1.2rem' : 0 }}>
          <div className="card__title" style={{ marginBottom: 0 }}>📋 Datos de la autorización</div>
          {!editando && (
            <div className="toolbar__actions">
              {!completa && (
                <button className="btn btn--ghost btn--sm" onClick={empezarEdicion}>Editar</button>
              )}
              <button className="btn btn--danger btn--sm" onClick={() => { setBorrando(true); setMotivo(''); setEliminadoPor(''); setClaveBorrar(''); setErrorBorrar('') }}>
                Eliminar
              </button>
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

      {borrando && (
        <div className="modal-fondo" onClick={() => !confirmando && setBorrando(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="card__title" style={{ marginBottom: '0.3rem' }}>🗑️ Eliminar solicitud #{solicitud.id}</div>
            <p className="card__hint">
              La solicitud se elimina de la lista, pero queda registrada en el historial de
              eliminaciones con este motivo. No se puede deshacer.
            </p>
            {completa && (
              <div className="alert alert--warning">
                Esta solicitud está <strong>autorizada</strong>. Solo administración puede eliminarla,
                con la clave.
              </div>
            )}
            {errorBorrar && <div className="alert alert--error">{errorBorrar}</div>}
            <div className="field">
              <label>Motivo de la eliminación <span style={{ color: 'var(--danger)' }}>*</span></label>
              <textarea
                autoFocus value={motivo} onChange={(e) => setMotivo(e.target.value)}
                placeholder="Ej: cargada por error, factura duplicada, se anuló la compra…"
              />
            </div>
            <div className="field">
              <label>Tu nombre (para el registro)</label>
              <input
                type="text" value={eliminadoPor} onChange={(e) => setEliminadoPor(e.target.value)}
                placeholder="Quién elimina"
              />
            </div>
            {completa && (
              <div className="field">
                <label>Clave de administración <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input
                  type="password" value={claveBorrar} onChange={(e) => setClaveBorrar(e.target.value)}
                  placeholder="Requerida para eliminar una autorizada"
                />
              </div>
            )}
            <div className="toolbar" style={{ marginBottom: 0, marginTop: '0.6rem' }}>
              <button className="btn btn--ghost" onClick={() => setBorrando(false)} disabled={confirmando}>
                Cancelar
              </button>
              <button className="btn btn--danger-solid" onClick={confirmarBorrado}
                      disabled={confirmando || !motivo.trim() || (completa && !claveBorrar.trim())}>
                {confirmando ? <><span className="spinner" /> Eliminando…</> : 'Eliminar definitivamente'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
