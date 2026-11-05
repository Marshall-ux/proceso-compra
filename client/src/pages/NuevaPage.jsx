import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FormularioSolicitud from '../components/FormularioSolicitud.jsx'
import SelectorAvisados from '../components/SelectorAvisados.jsx'
import { CONCEPTOS, cuitValido, fmtFechaHora, fmtImporte, irAlPrimerError, montoEnPesos } from '../constants.js'
import { abiertasSimilares, buscarProveedor, crearSolicitud, extraerFacturas } from '../services/api.js'

const VACIA = {
  fecha: '', empresa: '', marca: '', empresas: [], marcas: [], marca_otro: '', ubicacion: '',
  proveedor_tipo: '', proveedor_nombre: '',
  moneda: 'ARS', tipo_cambio: '',
  cuit: '', tipo_orden: '', duracion_orden: '', concepto: '', concepto_otro: '', monto_total: '',
  forma_pago: '', cbu: '', condicion_pago: '', condicion_dias: '', condicion_otras: '',
  contacto_nombre: '', contacto_telefono: '', contacto_mail: '', observaciones: '',
  solicitado_por: '', factura_numero: '',
  criticidad: '', criticidad_obs: '', requiere_oc: '', cbu_imagen: '',
  legajo_nombre: '', legajo_archivo: '', facturas: [], items: [],
  avisar_a: [],   // [id] del firmante elegido: el mail le llega solo a esa persona
}

// Lo que quien carga repite siempre: el navegador lo recuerda para la próxima.
const RECORDADOS = { solicitado_por: 'alta_solicitado_por', ubicacion: 'alta_ubicacion' }

const vacia = () => {
  const datos = { ...VACIA }
  for (const [campo, clave] of Object.entries(RECORDADOS)) {
    try {
      datos[campo] = localStorage.getItem(clave) || ''
    } catch {
      datos[campo] = ''
    }
  }
  return datos
}

const recordar = (datos) => {
  for (const [campo, clave] of Object.entries(RECORDADOS)) {
    try {
      if (datos[campo]) localStorage.setItem(clave, datos[campo])
    } catch {
      // sin almacenamiento del navegador, la próxima vez se tipea de nuevo
    }
  }
}

export default function NuevaPage() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [paso, setPaso] = useState(1)
  const [cargando, setCargando] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [arrastrando, setArrastrando] = useState(false)
  const [datos, setDatos] = useState(vacia)
  const [autocompletados, setAutocompletados] = useState([])
  const [aviso, setAviso] = useState('')
  const [errores, setErrores] = useState([])
  const [campos, setCampos] = useState({})   // errores por campo, que marca el servidor
  const irAlError = useRef(false)
  // Proveedor ya conocido por su CUIT (solicitudes anteriores): completa lo que falta.
  const [proveedor, setProveedor] = useState(null)
  const cuitBuscado = useRef('')
  const datosRef = useRef(datos)
  datosRef.current = datos
  // Órdenes abiertas del mismo CUIT, marca y concepto: se pregunta si es la misma
  // antes de crear otra solicitud (lo que corresponde es sumarle la factura como pago).
  const [similares, setSimilares] = useState([])

  const procesar = async (archivos) => {
    const lista = Array.from(archivos || []).filter((a) => a)
    if (lista.length === 0) return
    setCargando(true)
    setAviso('')
    setErrores([])
    try {
      const r = await extraerFacturas(lista)
      const leidos = Object.entries(r.datos || {}).filter(([, v]) => v !== '' && v !== 0).map(([k]) => k)
      setDatos({
        ...vacia(),
        ...r.datos,
        items: r.items || [],
        facturas: r.facturas || [],
      })
      setAutocompletados(leidos)
      if (r.error) setAviso(r.error)
      else if (leidos.length === 0) setAviso('No se pudo leer ningún dato de los PDF. Cargalos a mano.')
      else if (lista.length > 1) setAviso(`Se combinaron ${lista.length} facturas en una sola orden. Revisá los renglones y el monto.`)
      setPaso(2)
    } catch (e) {
      setAviso(e.message)
    } finally {
      setCargando(false)
    }
  }

  // Al tocar un campo con error, ese error se va; los demás quedan hasta volver a guardar.
  const cambiar = (nuevo) => {
    setCampos((c) => {
      const quedan = Object.fromEntries(Object.entries(c).filter(([k]) => nuevo[k] === datos[k]))
      return Object.keys(quedan).length === Object.keys(c).length ? c : quedan
    })
    setDatos(nuevo)
  }

  // Después de un intento fallido, lleva al primer campo marcado.
  useEffect(() => {
    if (!irAlError.current) return
    irAlError.current = false
    irAlPrimerError()
  }, [campos, errores])

  // Si se cierra o recarga la pestaña con la solicitud a medio cargar, el navegador pregunta.
  useEffect(() => {
    if (paso !== 2) return undefined
    const avisar = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', avisar)
    return () => window.removeEventListener('beforeunload', avisar)
  }, [paso])

  // Con un CUIT válido se buscan las solicitudes anteriores del proveedor y se completan
  // solos los datos vacíos (nunca se pisa lo que ya está cargado). Pasa tanto si se
  // tipea como si el CUIT viene de la factura.
  useEffect(() => {
    const digitos = String(datos.cuit || '').replace(/\D/g, '')
    if (!cuitValido(digitos)) {
      cuitBuscado.current = ''
      setProveedor(null)
      return undefined
    }
    if (digitos === cuitBuscado.current) return undefined
    cuitBuscado.current = digitos
    let vigente = true
    buscarProveedor(digitos).then((r) => {
      if (!vigente) return
      setProveedor(r)
      if (!r.encontrado) return
      const actual = datosRef.current
      // El CBU se completa recién si se elige transferencia (ver el efecto de abajo).
      const { cbu, cbu_imagen: cbuImagen, ...resto } = r.datos
      const nuevos = Object.fromEntries(Object.entries({ ...resto, proveedor_tipo: 'habitual' })
        .filter(([campo, valor]) => valor && !String(actual[campo] || '').trim()))
      if (Object.keys(nuevos).length === 0) return
      setDatos({ ...actual, ...nuevos })
      setAutocompletados((a) => [...new Set([...a, ...Object.keys(nuevos)])])
    }).catch(() => vigente && setProveedor(null))
    return () => { vigente = false }
  }, [datos.cuit])

  // El CBU de la última vez entra cuando se elige transferencia y no hay uno cargado.
  useEffect(() => {
    const anterior = proveedor?.encontrado ? proveedor.datos : null
    if (!anterior || !(anterior.cbu || anterior.cbu_imagen)) return
    if (!(datos.forma_pago || '').split(',').includes('transferencia')) return
    if (datos.cbu || datos.cbu_imagen) return
    setDatos((d) => ({ ...d, cbu: anterior.cbu || '', cbu_imagen: anterior.cbu_imagen || '' }))
    setAutocompletados((a) => [...new Set([...a, 'cbu'])])
  }, [datos.forma_pago, proveedor])  // eslint-disable-line react-hooks/exhaustive-deps

  const notaCuit = proveedor && (proveedor.encontrado
    ? <>Proveedor conocido: ya tiene {proveedor.solicitudes} solicitud{proveedor.solicitudes === 1 ? '' : 'es'} (la
        última, la #{proveedor.ultima_id}). Completamos los datos que faltaban: revisalos.</>
    : 'No hay solicitudes anteriores con este CUIT. Si es un proveedor nuevo, hace falta el legajo.')

  const guardar = async (esOtra = false) => {
    setGuardando(true)
    setErrores([])
    try {
      if (!esOtra) {
        const encontradas = await abiertasSimilares(datos.cuit, datos.marcas, datos.concepto)
        if (encontradas.length > 0) {
          setSimilares(encontradas)
          return
        }
      }
      setSimilares([])
      const creada = await crearSolicitud(datos)
      recordar(datos)
      navigate(`/solicitudes/${creada.id}`)
    } catch (e) {
      setErrores(e.data?.errores || [e.message])
      setCampos(e.data?.campos || {})
      irAlError.current = true
    } finally {
      setGuardando(false)
    }
  }

  // Es la misma orden: va a la existente con la factura lista para cargarla como pago.
  // Si todavía no está autorizada no admite pagos: se la muestra y se avisa.
  const usarExistente = (orden) => {
    navigate(`/solicitudes/${orden.id}`, {
      state: orden.estado === 'autorizada'
        ? { pagoInicial: {
            facturas: datos.facturas, monto: datos.monto_total || '', tipo_cambio: datos.tipo_cambio || '',
            fecha: datos.fecha || '', cargado_por: datos.solicitado_por || '',
          } }
        : { avisoDuplicada: true },
    })
  }

  const continuarSinFactura = () => {
    setDatos(vacia())
    setAutocompletados([])
    setPaso(2)
  }

  return (
    <>
      <div className="pasos">
        <div className={`paso ${paso === 1 ? 'paso--activo' : 'paso--hecho'}`}>
          <span className="paso__num">1</span> Subir factura
        </div>
        <span className="paso__sep" />
        <div className={`paso ${paso === 2 ? 'paso--activo' : ''}`}>
          <span className="paso__num">2</span> Revisar y completar
        </div>
        <span className="paso__sep" />
        <div className="paso"><span className="paso__num">3</span> Autorizar</div>
      </div>

      {paso === 1 && (
        <div className="card">
          <div className="card__title">📄 Subí la factura del proveedor</div>
          <div className="card__hint">
            Leemos los datos del PDF y completamos la autorización genérica. Podés subir
            varias facturas: se combinan en una sola orden. Después revisás todo antes de guardar.
          </div>
          {aviso && <div className="alert alert--error">{aviso}</div>}
          <div
            className={`dropzone ${arrastrando ? 'dropzone--active' : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setArrastrando(true) }}
            onDragLeave={() => setArrastrando(false)}
            onDrop={(e) => {
              e.preventDefault()
              setArrastrando(false)
              procesar(e.dataTransfer.files)
            }}
          >
            <div className="dropzone__icon">{cargando ? '⏳' : '📎'}</div>
            <div className="dropzone__title">
              {cargando ? 'Leyendo las facturas…' : 'Arrastrá los PDF o hacé clic para elegirlos'}
            </div>
            <div className="dropzone__hint">Uno o varios archivos PDF</div>
            <input
              ref={inputRef} type="file" accept="application/pdf" multiple
              onChange={(e) => procesar(e.target.files)}
            />
          </div>
          <div style={{ textAlign: 'center', marginTop: '1.2rem' }}>
            <button className="btn btn--ghost btn--sm" onClick={continuarSinFactura}>
              No tengo la factura, cargar a mano
            </button>
          </div>
        </div>
      )}

      {paso === 2 && (
        <div className="card">
          <div className="card__title">✏️ Revisá y completá la autorización</div>
          <div className="card__hint">
            Los campos en verde los completamos solos (de la factura o de solicitudes anteriores
            del proveedor): revisalos igual. Los que tienen <span className="obligatorio">*</span> son obligatorios.
            {datos.facturas?.length > 0 && (
              <> {datos.facturas.length === 1 ? 'Factura' : `${datos.facturas.length} facturas`}:{' '}
                <strong>{datos.facturas.map((f) => f.nombre).join(', ')}</strong>.</>
            )}
          </div>
          {aviso && <div className="alert alert--warning">{aviso}</div>}
          {errores.length > 0 && (
            Object.keys(campos).length > 0 ? (
              <div className="alert alert--error">
                {Object.keys(campos).length === 1
                  ? 'Falta revisar un dato: está marcado en rojo abajo.'
                  : `Faltan revisar ${Object.keys(campos).length} datos: están marcados en rojo abajo.`}
              </div>
            ) : (
              <div className="alert alert--error">
                Revisá estos puntos:
                <ul>{errores.map((e, i) => <li key={i}>{e}</li>)}</ul>
              </div>
            )
          )}

          <FormularioSolicitud
            datos={datos} onChange={cambiar} autocompletados={autocompletados}
            errores={campos} notaCuit={notaCuit}
          />

          <SelectorAvisados
            marcas={datos.marcas} valores={datos.avisar_a} error={campos.avisar_a}
            monto={montoEnPesos(datos.monto_total, datos.moneda, datos.tipo_cambio)}
            onChange={(avisar_a) => {
              setCampos(({ avisar_a: _, ...resto }) => resto)
              setDatos((d) => ({ ...d, avisar_a }))
            }}
          />

          <div className="toolbar" style={{ marginBottom: 0 }}>
            <button className="btn btn--ghost" onClick={() => setPaso(1)}>← Volver</button>
            <button className="btn btn--primary" onClick={() => guardar()} disabled={guardando}>
              {guardando ? <><span className="spinner" /> Guardando…</> : 'Guardar y pasar a autorización →'}
            </button>
          </div>
        </div>
      )}

      {similares.length > 0 && (
        <div className="modal-fondo" onClick={() => setSimilares([])}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="card__title" style={{ marginBottom: '0.3rem' }}>
              ⚠ Ya hay {similares.length === 1 ? 'una orden abierta' : `${similares.length} órdenes abiertas`} para este proveedor
            </div>
            <p className="card__hint">
              Mismo CUIT, marca y concepto. Si esta factura es de esa orden, no hay que crear
              una solicitud nueva: se agrega como pago a la orden existente.
            </p>
            {similares.map((o) => (
              <div key={o.id} className="alert alert--info" style={{ display: 'block' }}>
                <strong>#{o.id} · {o.proveedor_nombre}</strong> (CUIT {o.cuit})
                <div>
                  {o.marcas.join(', ')} · {CONCEPTOS.find((c) => c.valor === o.concepto)?.etiqueta || o.concepto}
                  {' '}· {fmtImporte(o.monto_total, o.moneda)}
                </div>
                <div>
                  Cargada el {fmtFechaHora(o.created_at)}{o.duracion_orden && <> · duración {o.duracion_orden}</>}
                  {' '}· {o.estado === 'autorizada' ? 'autorizada' : 'pendiente de firma'}
                </div>
                <button className="btn btn--primary btn--sm" style={{ marginTop: '0.6rem' }}
                        onClick={() => usarExistente(o)}>
                  {o.estado === 'autorizada' ? `Sí, agregarla como pago a #${o.id}` : `Sí, es esta: ver #${o.id}`}
                </button>
              </div>
            ))}
            <div className="toolbar" style={{ marginBottom: 0, marginTop: '0.6rem' }}>
              <button className="btn btn--ghost" onClick={() => setSimilares([])}>Volver al formulario</button>
              <button className="btn btn--ghost" onClick={() => guardar(true)} disabled={guardando}>
                No, es otra: crear solicitud nueva
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
