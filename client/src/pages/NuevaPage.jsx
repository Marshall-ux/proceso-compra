import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FormularioSolicitud from '../components/FormularioSolicitud.jsx'
import { crearSolicitud, extraerFacturas } from '../services/api.js'

const VACIA = {
  fecha: '', empresa: '', marca: '', marca_otro: '', proveedor_tipo: '', proveedor_nombre: '',
  cuit: '', tipo_orden: '', duracion_orden: '', concepto: '', concepto_otro: '', monto_total: '',
  forma_pago: '', cbu: '', condicion_pago: '', condicion_dias: '', condicion_otras: '',
  contacto_nombre: '', contacto_telefono: '', contacto_mail: '', observaciones: '',
  solicitado_por: '', factura_numero: '',
  criticidad: '', criticidad_obs: '', requiere_oc: '', cbu_imagen: '',
  legajo_nombre: '', legajo_archivo: '', facturas: [], items: [],
}

export default function NuevaPage() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [paso, setPaso] = useState(1)
  const [cargando, setCargando] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [arrastrando, setArrastrando] = useState(false)
  const [datos, setDatos] = useState(VACIA)
  const [autocompletados, setAutocompletados] = useState([])
  const [aviso, setAviso] = useState('')
  const [errores, setErrores] = useState([])

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
        ...VACIA,
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

  const guardar = async () => {
    setGuardando(true)
    setErrores([])
    try {
      const creada = await crearSolicitud(datos)
      navigate(`/solicitudes/${creada.id}`)
    } catch (e) {
      setErrores(e.data?.errores || [e.message])
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } finally {
      setGuardando(false)
    }
  }

  const continuarSinFactura = () => {
    setDatos(VACIA)
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
            Los campos en verde los leímos de la factura: revisalos igual.
            {datos.facturas?.length > 0 && (
              <> {datos.facturas.length === 1 ? 'Factura' : `${datos.facturas.length} facturas`}:{' '}
                <strong>{datos.facturas.map((f) => f.nombre).join(', ')}</strong>.</>
            )}
          </div>
          {aviso && <div className="alert alert--warning">{aviso}</div>}
          {errores.length > 0 && (
            <div className="alert alert--error">
              Revisá estos puntos:
              <ul>{errores.map((e, i) => <li key={i}>{e}</li>)}</ul>
            </div>
          )}

          <FormularioSolicitud datos={datos} onChange={setDatos} autocompletados={autocompletados} />

          <div className="toolbar" style={{ marginBottom: 0 }}>
            <button className="btn btn--ghost" onClick={() => setPaso(1)}>← Volver</button>
            <button className="btn btn--primary" onClick={guardar} disabled={guardando}>
              {guardando ? <><span className="spinner" /> Guardando…</> : 'Guardar y pasar a autorización →'}
            </button>
          </div>
        </div>
      )}
    </>
  )
}
