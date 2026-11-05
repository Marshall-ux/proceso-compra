import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import CambioTipoOrden from '../components/CambioTipoOrden.jsx'
import FormularioSolicitud from '../components/FormularioSolicitud.jsx'
import PanelAutorizacion from '../components/PanelAutorizacion.jsx'
import ResumenSolicitud from '../components/ResumenSolicitud.jsx'
import SeccionPagos from '../components/SeccionPagos.jsx'
import SelectorAvisados from '../components/SelectorAvisados.jsx'
import { UBICACIONES, estadoDe, fmtFechaHora, fmtImporte, fmtMoney, montoEnPesos } from '../constants.js'
import {
  actualizarSolicitud, eliminarSolicitud, obtenerSolicitud,
  urlCbuImagen, urlFactura, urlLegajo, urlPdf, urlPdfCompleto, urlZip,
} from '../services/api.js'

export default function DetallePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  // Viene del alta, cuando la factura resultó ser de esta orden abierta (ver NuevaPage).
  const [desdeAlta] = useState(() => location.state || {})
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
  const [verFormulario, setVerFormulario] = useState(false)   // PDF embebido, a pedido

  const cargar = useCallback(async () => {
    try {
      setSolicitud(await obtenerSolicitud(id))
    } catch (e) {
      setError(e.message)
    }
  }, [id])

  useEffect(() => { cargar() }, [cargar])

  // El estado de navegación se consume una vez: recargar la página no reabre el pago.
  useEffect(() => {
    if (location.state) navigate(location.pathname, { replace: true, state: null })
  }, [location, navigate])

  if (error) return <div className="alert alert--error">{error}</div>
  if (!solicitud) return <div className="empty"><span className="spinner spinner--dark" /> Cargando…</div>

  const completa = solicitud.estado === 'autorizada'
  const pendiente = solicitud.estado === 'pendiente'
  // Una devuelta se corrige editándola; autorizadas y rechazadas quedan como registro.
  const editable = pendiente || solicitud.estado === 'observada'
  const requiereClave = completa || solicitud.estado === 'rechazada'
  const revision = (solicitud.revisiones || []).at(-1)
  const devueltaORechazada = ['observada', 'rechazada'].includes(solicitud.estado) && revision

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
    if (requiereClave && !claveBorrar.trim()) {
      setErrorBorrar(`Está ${solicitud.estado}: ingresá la clave de administración para eliminarla.`)
      return
    }
    setConfirmando(true)
    try {
      await eliminarSolicitud(id, { motivo: motivo.trim(), eliminado_por: eliminadoPor.trim() },
                              requiereClave ? claveBorrar.trim() : undefined)
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
            <span className={`badge badge--${estadoDe(solicitud.estado).badge}`}>
              {solicitud.requiere_segunda_firma ? 'Pendiente · falta 2ª firma' : estadoDe(solicitud.estado).etiqueta}
            </span>
          </h1>
          <div className="toolbar__info">
            {solicitud.proveedor_nombre} · {solicitud.marca}
            {solicitud.ubicacion && <> · {UBICACIONES.find((u) => u.valor === solicitud.ubicacion)?.etiqueta || solicitud.ubicacion}</>}
            {' '}· {fmtImporte(solicitud.monto_total, solicitud.moneda)}
            {solicitud.moneda === 'USD' && <> (TC {fmtMoney(solicitud.tipo_cambio)} = $ {fmtMoney(solicitud.monto_pesos)})</>}
            {solicitud.criticidad === 'urgente' && <> · <span className="badge badge--danger">Urgente</span></>}
            {solicitud.avisados?.length > 0 && (
              <> · 📧 {solicitud.avisados.length === 1 ? 'Firmante elegido' : 'Aviso a'}: {solicitud.avisados.join(', ')}</>
            )}
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

      {desdeAlta.pagoInicial && (
        <div className="alert alert--info">
          La factura que estabas cargando quedó lista como pago de esta orden abierta:
          completá la descripción y agregala abajo, en "Pagos imputados".
        </div>
      )}
      {desdeAlta.avisoDuplicada && (
        <div className="alert alert--warning">
          Esta orden abierta todavía está pendiente de firma. Cuando quede autorizada,
          sumale la factura como pago desde esta pantalla, sin crear una solicitud nueva.
        </div>
      )}

      {devueltaORechazada && (
        <div className={`alert alert--${solicitud.estado === 'rechazada' ? 'error' : 'warning'}`}>
          <strong>{solicitud.estado === 'rechazada' ? 'Rechazada' : 'Devuelta para corregir'}</strong>
          {' '}por {revision.nombre} el {fmtFechaHora(revision.fecha)}: «{revision.motivo}»
          <div style={{ marginTop: '0.3rem' }}>
            {solicitud.estado === 'rechazada'
              ? 'Una solicitud rechazada no se firma ni se edita: queda como registro.'
              : <>Corregila con <strong>Editar</strong>: al guardar vuelve a firma y a {revision.nombre} le llega el aviso.</>}
          </div>
        </div>
      )}

      {/* Primero lo que se firma, después la firma. */}
      <div className="card">
        <div className="toolbar" style={{ marginBottom: '1.2rem' }}>
          <div className="card__title" style={{ marginBottom: 0 }}>📋 Datos de la autorización</div>
          {!editando && (
            <div className="toolbar__actions">
              {editable && (
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
            {/* Solo firma el elegido: si cambió la marca o el monto, o el elegido ya no
                puede firmar, acá se elige otro y le llega el mail. */}
            <SelectorAvisados
              marcas={borrador.marcas} valores={borrador.avisar_a || []}
              monto={montoEnPesos(borrador.monto_total, borrador.moneda, borrador.tipo_cambio)}
              onChange={(avisar_a) => setBorrador((d) => ({ ...d, avisar_a }))}
            />
            <div className="toolbar" style={{ marginBottom: 0 }}>
              <button className="btn btn--ghost" onClick={() => setEditando(false)}>Cancelar</button>
              <button className="btn btn--primary" onClick={guardar} disabled={guardando}>
                {guardando ? <><span className="spinner" /> Guardando…</> : 'Guardar cambios'}
              </button>
            </div>
          </>
        ) : (
          <>
            <ResumenSolicitud solicitud={solicitud} />
            {/* El formulario oficial embebido queda a pedido: en el celular un PDF dentro
                de la página suele no verse (para eso está "Ver PDF" arriba). */}
            <button className="btn btn--ghost btn--sm" style={{ marginTop: '1rem' }}
                    onClick={() => setVerFormulario((v) => !v)}>
              {verFormulario ? 'Ocultar el formulario oficial' : 'Ver el formulario oficial acá'}
            </button>
            {verFormulario && (
              <iframe className="visor" style={{ marginTop: '0.9rem' }} src={urlPdf(solicitud.id)}
                      title={`Autorización ${solicitud.id}`} />
            )}
          </>
        )}
      </div>

      <PanelAutorizacion solicitud={solicitud} onActualizar={setSolicitud} />

      {pendiente && <CambioTipoOrden solicitud={solicitud} onActualizar={setSolicitud} />}

      {completa && (
        <SeccionPagos solicitud={solicitud} onActualizar={setSolicitud}
                      pagoInicial={desdeAlta.pagoInicial} />
      )}

      {borrando && (
        <div className="modal-fondo" onClick={() => !confirmando && setBorrando(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="card__title" style={{ marginBottom: '0.3rem' }}>🗑️ Eliminar solicitud #{solicitud.id}</div>
            <p className="card__hint">
              La solicitud se elimina de la lista, pero queda registrada en el historial de
              eliminaciones con este motivo. No se puede deshacer.
            </p>
            {requiereClave && (
              <div className="alert alert--warning">
                Esta solicitud está <strong>{solicitud.estado}</strong>. Solo administración puede
                eliminarla, con la clave.
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
            {requiereClave && (
              <div className="field">
                <label>Clave de administración <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input
                  type="password" value={claveBorrar} onChange={(e) => setClaveBorrar(e.target.value)}
                  placeholder={`Requerida para eliminar una ${solicitud.estado}`}
                />
              </div>
            )}
            <div className="toolbar" style={{ marginBottom: 0, marginTop: '0.6rem' }}>
              <button className="btn btn--ghost" onClick={() => setBorrando(false)} disabled={confirmando}>
                Cancelar
              </button>
              <button className="btn btn--danger-solid" onClick={confirmarBorrado}
                      disabled={confirmando || !motivo.trim() || (requiereClave && !claveBorrar.trim())}>
                {confirmando ? <><span className="spinner" /> Eliminando…</> : 'Eliminar definitivamente'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
