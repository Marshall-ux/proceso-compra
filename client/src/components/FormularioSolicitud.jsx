import {
  CONCEPTOS, CONDICION_DIAS, CONDICION_PAGO, CRITICIDAD, EMPRESAS, FORMA_PAGO, MARCAS,
  PROVEEDOR_TIPO, REQUIERE_OC, TIPO_ORDEN, fmtMoney,
} from '../constants.js'
import { subirCbu, subirLegajo } from '../services/api.js'
import AdjuntoUploader from './AdjuntoUploader.jsx'
import ItemsEditor from './ItemsEditor.jsx'
import Opciones from './Opciones.jsx'

// Reproduce el formulario F 8.4-01 Rev.07, en el mismo orden que el papel.
// `autocompletados` son los campos que se leyeron de la factura: se resaltan para
// que el empleado sepa que revisar.
export default function FormularioSolicitud({ datos, onChange, autocompletados = [] }) {
  const set = (campo) => (valor) => onChange({ ...datos, [campo]: valor })
  const setInput = (campo) => (e) => onChange({ ...datos, [campo]: e.target.value })
  const auto = (campo) => (autocompletados.includes(campo) ? 'field field--autocompletado' : 'field')

  const suma = (datos.items || []).reduce((acc, it) => acc + (Number(it.total) || 0), 0)
  const difiere = Math.abs(suma - (Number(datos.monto_total) || 0)) > 0.5 && suma > 0

  return (
    <>
      <div className="seccion">
        <div className="seccion__titulo">Fecha y empresa a la que debe imputarse el pago</div>
        <div className="grid grid--2">
          <div className={auto('fecha')}>
            <label>Fecha</label>
            <input type="text" placeholder="dd/mm/aaaa" value={datos.fecha || ''} onChange={setInput('fecha')} />
          </div>
        </div>
        <div style={{ marginTop: '0.9rem' }}>
          <Opciones nombre="empresa" valor={datos.empresa} opciones={EMPRESAS} onChange={set('empresa')} />
        </div>
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Marca</div>
        <Opciones nombre="marca" valor={datos.marca} opciones={MARCAS} onChange={set('marca')} />
        {datos.marca === 'OTRO' && (
          <div className="field" style={{ marginTop: '0.7rem' }}>
            <label>¿Cuál?</label>
            <input type="text" value={datos.marca_otro || ''} onChange={setInput('marca_otro')} />
          </div>
        )}
        <div className="field__nota">La marca define quiénes pueden autorizar esta compra.</div>
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Datos del proveedor y tipo de orden</div>
        <Opciones nombre="proveedor_tipo" valor={datos.proveedor_tipo} opciones={PROVEEDOR_TIPO} onChange={set('proveedor_tipo')} />
        {datos.proveedor_tipo === 'nuevo' && (
          <div className="alert alert--info" style={{ marginTop: '0.7rem' }}>
            <strong>Importante:</strong> al ser un nuevo proveedor debe presentar legajo impositivo,
            constancia de inscripción, formulario 1276/CM05 convenio y formulario de exención si lo tuviera.
          </div>
        )}
        <div className="grid grid--2" style={{ marginTop: '0.9rem' }}>
          <div className={auto('proveedor_nombre')}>
            <label>Nombre del proveedor</label>
            <input type="text" value={datos.proveedor_nombre || ''} onChange={setInput('proveedor_nombre')} />
          </div>
          <div className={auto('cuit')}>
            <label>CUIT</label>
            <input type="text" placeholder="00-00000000-0" value={datos.cuit || ''} onChange={setInput('cuit')} />
          </div>
        </div>
        <div style={{ marginTop: '0.9rem' }}>
          <Opciones nombre="tipo_orden" valor={datos.tipo_orden} opciones={TIPO_ORDEN} onChange={set('tipo_orden')} />
        </div>
        {datos.tipo_orden === 'abierta' && (
          <div className="field" style={{ marginTop: '0.7rem' }}>
            <label>Duración de la orden abierta</label>
            <input type="text" placeholder="Ej: 6 meses" value={datos.duracion_orden || ''} onChange={setInput('duracion_orden')} />
          </div>
        )}
        <div style={{ marginTop: '0.9rem' }}>
          <AdjuntoUploader
            label="Legajo impositivo (PDF)"
            hint={datos.proveedor_tipo === 'nuevo'
              ? 'Obligatorio para proveedores nuevos.' : 'Opcional. Lo carga el comprador o el responsable de proveedores.'}
            accept="application/pdf"
            nombre={datos.legajo_nombre}
            onSubir={subirLegajo}
            onListo={(r) => onChange({ ...datos, legajo_archivo: r.archivo, legajo_nombre: r.nombre })}
            onQuitar={() => onChange({ ...datos, legajo_archivo: '', legajo_nombre: '' })}
          />
        </div>
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Prioridad del pago y orden de compra</div>
        <div className="grid grid--2">
          <div className="field">
            <label>Criticidad (qué tan urgente es el pago)</label>
            <Opciones nombre="criticidad" valor={datos.criticidad} opciones={CRITICIDAD} onChange={set('criticidad')} />
          </div>
          <div className="field">
            <label>¿Requiere orden de compra?</label>
            <Opciones nombre="requiere_oc" valor={datos.requiere_oc} opciones={REQUIERE_OC} onChange={set('requiere_oc')} />
          </div>
        </div>
        {datos.criticidad === 'otro' && (
          <div className="field" style={{ marginTop: '0.7rem' }}>
            <label>Detalle de la criticidad</label>
            <input type="text" placeholder="Ej: pagar antes de fin de mes" value={datos.criticidad_obs || ''} onChange={setInput('criticidad_obs')} />
          </div>
        )}
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Concepto del pago</div>
        <Opciones nombre="concepto" valor={datos.concepto} opciones={CONCEPTOS} onChange={set('concepto')} />
        {datos.concepto === 'otros' && (
          <div className="field" style={{ marginTop: '0.7rem' }}>
            <label>¿Cuál?</label>
            <input type="text" value={datos.concepto_otro || ''} onChange={setInput('concepto_otro')} />
          </div>
        )}
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Detalle del servicio o producto</div>
        {datos.facturas?.length > 0 && (
          <div className="field__nota" style={{ marginBottom: '0.7rem' }}>
            Facturas adjuntas: {datos.facturas.map((f) => f.nombre).join(', ')}
          </div>
        )}
        {(datos.items || []).length > 6 && (
          <div className="alert alert--warning">
            El formulario oficial tiene 6 renglones y esta orden tiene {(datos.items || []).length}.
            En el PDF entran los primeros 6; agrupá o resumí los ítems si hace falta que se vean todos.
          </div>
        )}
        <ItemsEditor items={datos.items || []} onChange={set('items')} />
        <div className="grid grid--2" style={{ marginTop: '1.1rem' }}>
          <div className={auto('monto_total')}>
            <label>Monto presupuesto final (IVA incluido)</label>
            <input
              type="number" step="0.01"
              value={datos.monto_total ?? ''}
              onChange={(e) => onChange({ ...datos, monto_total: e.target.value })}
            />
            {difiere && (
              <div className="field__nota" style={{ color: 'var(--warning)' }}>
                Los renglones suman $ {fmtMoney(suma)}. Es normal si el monto final incluye IVA.
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Forma de pago</div>
        <Opciones nombre="forma_pago" valor={datos.forma_pago} opciones={FORMA_PAGO} onChange={set('forma_pago')} />
        {datos.forma_pago === 'transferencia' && (
          <div className="grid grid--2" style={{ marginTop: '0.7rem' }}>
            <div className={auto('cbu')}>
              <label>CBU (número)</label>
              <input type="text" value={datos.cbu || ''} onChange={setInput('cbu')} />
            </div>
            <AdjuntoUploader
              label="CBU (imagen JPG/PNG)"
              hint="Podés cargar el número, la imagen, o ambos."
              accept="image/jpeg,image/png"
              nombre={datos.cbu_imagen ? 'Imagen cargada' : ''}
              onSubir={subirCbu}
              onListo={(r) => onChange({ ...datos, cbu_imagen: r.archivo })}
              onQuitar={() => onChange({ ...datos, cbu_imagen: '' })}
            />
          </div>
        )}
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Condiciones de pago</div>
        <Opciones nombre="condicion_pago" valor={datos.condicion_pago} opciones={CONDICION_PAGO} onChange={set('condicion_pago')} />
        {datos.condicion_pago === 'cuenta_corriente' && (
          <div className="grid grid--2" style={{ marginTop: '0.7rem' }}>
            <div className="field">
              <label>Plazo</label>
              <div className="opciones">
                {CONDICION_DIAS.map((d) => (
                  <label key={d} className={`opcion ${datos.condicion_dias === d ? 'opcion--activa' : ''}`}>
                    <input
                      type="radio" name="condicion_dias"
                      checked={datos.condicion_dias === d}
                      onChange={() => set('condicion_dias')(d)}
                    />
                    {d} días
                  </label>
                ))}
              </div>
            </div>
            <div className="field">
              <label>Otro plazo (días)</label>
              <input
                type="text" placeholder="Ej: 45"
                value={CONDICION_DIAS.includes(datos.condicion_dias) ? '' : (datos.condicion_dias || '')}
                onChange={setInput('condicion_dias')}
              />
            </div>
          </div>
        )}
        {datos.condicion_pago === 'otras' && (
          <div className="field" style={{ marginTop: '0.7rem' }}>
            <label>¿Cuáles?</label>
            <input type="text" value={datos.condicion_otras || ''} onChange={setInput('condicion_otras')} />
          </div>
        )}
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Contacto con el proveedor</div>
        <div className="grid grid--3">
          <div className="field">
            <label>Nombre de contacto</label>
            <input type="text" value={datos.contacto_nombre || ''} onChange={setInput('contacto_nombre')} />
          </div>
          <div className={auto('contacto_telefono')}>
            <label>Teléfono</label>
            <input type="text" value={datos.contacto_telefono || ''} onChange={setInput('contacto_telefono')} />
          </div>
          <div className={auto('contacto_mail')}>
            <label>Mail</label>
            <input type="text" value={datos.contacto_mail || ''} onChange={setInput('contacto_mail')} />
          </div>
        </div>
        <div className="field" style={{ marginTop: '0.9rem' }}>
          <label>Observaciones</label>
          <textarea value={datos.observaciones || ''} onChange={setInput('observaciones')} />
        </div>
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Compra o contratación solicitada por</div>
        <div className="grid grid--2">
          <div className="field">
            <label>Nombre y apellido de quien solicita</label>
            <input type="text" value={datos.solicitado_por || ''} onChange={setInput('solicitado_por')} />
          </div>
        </div>
      </div>
    </>
  )
}
