import {
  CONCEPTOS, CONDICION_DIAS, CONDICION_PAGO, CRITICIDAD, EMPRESAS, FORMA_PAGO, MARCAS,
  MONEDAS, PROVEEDOR_TIPO, REQUIERE_OC, TIPO_ORDEN, UBICACIONES, cuitValido, fmtImporte, fmtMoney,
  montoEnPesos,
} from '../constants.js'
import { subirCbu, subirLegajo } from '../services/api.js'
import AdjuntoUploader from './AdjuntoUploader.jsx'
import ItemsEditor from './ItemsEditor.jsx'
import MultiOpciones from './MultiOpciones.jsx'
import Opciones from './Opciones.jsx'

const OBLIGATORIO = <span className="obligatorio" title="Obligatorio">*</span>

// Reproduce el formulario F 8.4-01 Rev.07 en el orden del papel, salvo el CUIT, que va
// antes que el nombre: con el CUIT se completan los datos de un proveedor ya conocido.
// `autocompletados` son los campos que se leyeron de la factura (o de solicitudes
// anteriores del proveedor): se resaltan para que el empleado sepa qué revisar.
// `errores` ({campo: mensaje}) los marca el servidor al guardar: cada uno se muestra
// debajo de su campo, y `data-campo` es por donde la pantalla lleva al primero.
// `notaCuit` es lo que se sabe del proveedor por su CUIT (lo arma la pantalla de alta).
export default function FormularioSolicitud({ datos, onChange, autocompletados = [], errores = {}, notaCuit = null }) {
  const set = (campo) => (valor) => onChange({ ...datos, [campo]: valor })
  const setInput = (campo) => (e) => onChange({ ...datos, [campo]: e.target.value })
  const clase = (campo) => ['field', autocompletados.includes(campo) && 'field--autocompletado',
    errores[campo] && 'field--error'].filter(Boolean).join(' ')
  const grupo = (campo) => (errores[campo] ? 'grupo grupo--error' : 'grupo')
  const marca = (campo) => ({ 'data-campo': campo, 'data-error': errores[campo] ? 'si' : undefined })
  const error = (campo) => (errores[campo] ? <div className="field__error">{errores[campo]}</div> : null)

  // forma_pago se guarda como texto separado por comas ("cheque,transferencia").
  const formasPago = (datos.forma_pago || '').split(',').filter(Boolean)
  const setFormasPago = (lista) => onChange({
    ...datos,
    forma_pago: FORMA_PAGO.map((o) => o.valor).filter((v) => lista.includes(v)).join(','),
  })

  const suma = (datos.items || []).reduce((acc, it) => acc + (Number(it.total) || 0), 0)
  const difiere = Math.abs(suma - (Number(datos.monto_total) || 0)) > 0.5 && suma > 0
  const moneda = datos.moneda || 'ARS'
  const enPesos = montoEnPesos(datos.monto_total, moneda, datos.tipo_cambio)
  // Mientras se tipea: con los 11 números ya se puede saber si el CUIT cierra.
  const digitosCuit = String(datos.cuit || '').replace(/\D/g, '')
  const cuitMal = digitosCuit.length === 11 && !cuitValido(digitosCuit)

  return (
    <>
      <div className="seccion">
        <div className="seccion__titulo">Fecha y empresa a la que debe imputarse el pago {OBLIGATORIO}</div>
        <div className="grid grid--2">
          <div className={clase('fecha')} {...marca('fecha')}>
            <label>Fecha de la factura {OBLIGATORIO}</label>
            <input type="text" placeholder="dd/mm/aaaa" value={datos.fecha || ''} onChange={setInput('fecha')} />
            {error('fecha')}
          </div>
        </div>
        <div className={grupo('empresas')} style={{ marginTop: '0.9rem' }} {...marca('empresas')}>
          <MultiOpciones nombre="empresas" valores={datos.empresas} opciones={EMPRESAS} onChange={set('empresas')} />
          {error('empresas')}
        </div>
        <div className="field__nota">
          Podés tildar varias: cuando un mismo gasto se imputa a varias empresas del grupo.
        </div>
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Marca {OBLIGATORIO}</div>
        <div className={grupo('marcas')} {...marca('marcas')}>
          <MultiOpciones nombre="marcas" valores={datos.marcas} opciones={MARCAS} onChange={set('marcas')} />
          {error('marcas')}
        </div>
        {(datos.marcas || []).includes('OTRO') && (
          <div className={clase('marca_otro')} style={{ marginTop: '0.7rem' }} {...marca('marca_otro')}>
            <label>¿Cuál? {OBLIGATORIO}</label>
            <input type="text" value={datos.marca_otro || ''} onChange={setInput('marca_otro')} />
            {error('marca_otro')}
          </div>
        )}
        <div className="field__nota">
          La marca define quiénes pueden autorizar. Si tildás varias, solo puede autorizar
          quien las cubra todas (Multimarca o dirección).
        </div>
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Ubicación {OBLIGATORIO}</div>
        <div className={grupo('ubicacion')} {...marca('ubicacion')}>
          <Opciones nombre="ubicacion" valor={datos.ubicacion} opciones={UBICACIONES} onChange={set('ubicacion')} />
          {error('ubicacion')}
        </div>
        <div className="field__nota">
          Junto con la empresa, define a qué cajera le llega el aviso cuando la solicitud queda autorizada.
        </div>
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Datos del proveedor y tipo de orden</div>
        <div className="grid grid--2">
          <div className={clase('cuit')} {...marca('cuit')}>
            <label>CUIT {OBLIGATORIO}</label>
            <input type="text" placeholder="00-00000000-0" value={datos.cuit || ''} onChange={setInput('cuit')} />
            {error('cuit') || (cuitMal && (
              <div className="field__error">Revisá el CUIT: el último número no coincide con los demás.</div>
            ))}
            {!errores.cuit && !cuitMal && notaCuit && <div className="field__nota">{notaCuit}</div>}
          </div>
          <div className={clase('proveedor_nombre')} {...marca('proveedor_nombre')}>
            <label>Nombre del proveedor {OBLIGATORIO}</label>
            <input type="text" value={datos.proveedor_nombre || ''} onChange={setInput('proveedor_nombre')} />
            {error('proveedor_nombre')}
          </div>
        </div>
        <div className={`field ${grupo('proveedor_tipo')}`} style={{ marginTop: '0.9rem' }} {...marca('proveedor_tipo')}>
          <label>Tipo de proveedor {OBLIGATORIO}</label>
          <Opciones nombre="proveedor_tipo" valor={datos.proveedor_tipo} opciones={PROVEEDOR_TIPO} onChange={set('proveedor_tipo')} />
          {error('proveedor_tipo')}
        </div>
        {datos.proveedor_tipo === 'nuevo' && (
          <div className="alert alert--info" style={{ marginTop: '0.7rem' }}>
            <strong>Importante:</strong> al ser un nuevo proveedor debe presentar legajo impositivo,
            constancia de inscripción, formulario 1276/CM05 convenio y formulario de exención si lo tuviera.
          </div>
        )}
        <div style={{ marginTop: '0.9rem' }} className={errores.legajo_archivo ? 'grupo grupo--error' : undefined}
             {...marca('legajo_archivo')}>
          <AdjuntoUploader
            label={<>Legajo impositivo (PDF) {datos.proveedor_tipo === 'nuevo' && OBLIGATORIO}</>}
            hint={datos.proveedor_tipo === 'nuevo'
              ? 'Obligatorio para proveedores nuevos.' : 'Opcional. Lo carga el comprador o el responsable de proveedores.'}
            accept="application/pdf"
            nombre={datos.legajo_nombre}
            onSubir={subirLegajo}
            onListo={(r) => onChange({ ...datos, legajo_archivo: r.archivo, legajo_nombre: r.nombre })}
            onQuitar={() => onChange({ ...datos, legajo_archivo: '', legajo_nombre: '' })}
          />
          {error('legajo_archivo')}
        </div>
        <div className={`field ${grupo('tipo_orden')}`} style={{ marginTop: '0.9rem' }} {...marca('tipo_orden')}>
          <label>Tipo de orden {OBLIGATORIO}</label>
          <Opciones nombre="tipo_orden" valor={datos.tipo_orden} opciones={TIPO_ORDEN} onChange={set('tipo_orden')} />
          {error('tipo_orden')}
        </div>
        {datos.tipo_orden === 'abierta' && (
          <div className={clase('duracion_orden')} style={{ marginTop: '0.7rem' }} {...marca('duracion_orden')}>
            <label>Duración de la orden abierta {OBLIGATORIO}</label>
            <input type="text" placeholder="Ej: 6 meses" value={datos.duracion_orden || ''} onChange={setInput('duracion_orden')} />
            {error('duracion_orden')}
          </div>
        )}
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Prioridad del pago y orden de compra</div>
        <div className="grid grid--2">
          <div className={`field ${grupo('criticidad')}`} {...marca('criticidad')}>
            <label>Criticidad (qué tan urgente es el pago) {OBLIGATORIO}</label>
            <Opciones nombre="criticidad" valor={datos.criticidad} opciones={CRITICIDAD} onChange={set('criticidad')} />
            {error('criticidad')}
          </div>
          <div className="field">
            <label>¿Requiere orden de compra?</label>
            <Opciones nombre="requiere_oc" valor={datos.requiere_oc} opciones={REQUIERE_OC} onChange={set('requiere_oc')} />
          </div>
        </div>
        {datos.criticidad === 'otro' && (
          <div className={clase('criticidad_obs')} style={{ marginTop: '0.7rem' }} {...marca('criticidad_obs')}>
            <label>Detalle de la criticidad {OBLIGATORIO}</label>
            <input type="text" placeholder="Ej: pagar antes de fin de mes" value={datos.criticidad_obs || ''} onChange={setInput('criticidad_obs')} />
            {error('criticidad_obs')}
          </div>
        )}
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Concepto del pago {OBLIGATORIO}</div>
        <div className={grupo('concepto')} {...marca('concepto')}>
          <Opciones nombre="concepto" valor={datos.concepto} opciones={CONCEPTOS} onChange={set('concepto')} />
          {error('concepto')}
        </div>
        {datos.concepto === 'otros' && (
          <div className={clase('concepto_otro')} style={{ marginTop: '0.7rem' }} {...marca('concepto_otro')}>
            <label>¿Cuál? {OBLIGATORIO}</label>
            <input type="text" value={datos.concepto_otro || ''} onChange={setInput('concepto_otro')} />
            {error('concepto_otro')}
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
        <ItemsEditor items={datos.items || []} onChange={set('items')} moneda={moneda} />
        <div style={{ marginTop: '1.1rem' }} className={clase('moneda')} {...marca('moneda')}>
          <Opciones
            nombre="moneda" valor={moneda} opciones={MONEDAS}
            onChange={(m) => onChange({ ...datos, moneda: m, tipo_cambio: m === 'USD' ? datos.tipo_cambio : '' })}
          />
          {error('moneda')}
        </div>
        <div className="grid grid--2" style={{ marginTop: '0.9rem' }}>
          <div className={clase('monto_total')} {...marca('monto_total')}>
            <label>Monto presupuesto final (IVA incluido){moneda === 'USD' ? ' en dólares' : ''} {OBLIGATORIO}</label>
            <input
              type="number" step="0.01"
              value={datos.monto_total ?? ''}
              onChange={(e) => onChange({ ...datos, monto_total: e.target.value })}
            />
            {error('monto_total')}
            {difiere && (
              <div className="field__nota" style={{ color: 'var(--warning)' }}>
                Los renglones suman {fmtImporte(suma, moneda)}. Es normal si el monto final incluye IVA.
              </div>
            )}
          </div>
          {moneda === 'USD' && (
            <div className={clase('tipo_cambio')} {...marca('tipo_cambio')}>
              <label>Tipo de cambio (pesos por dólar) {OBLIGATORIO}</label>
              <input
                type="number" step="0.01" placeholder="Ej: 1050"
                value={datos.tipo_cambio || ''}
                onChange={setInput('tipo_cambio')}
              />
              {error('tipo_cambio')}
              <div className="field__nota">
                {enPesos > 0
                  ? <>Equivale a <strong>$ {fmtMoney(enPesos)}</strong>. Con este monto se controla el tope de quien firma.</>
                  : 'Hace falta para comparar con los topes de firma, que están en pesos.'}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="seccion">
        <div className="seccion__titulo">Forma de pago</div>
        <MultiOpciones nombre="forma_pago" valores={formasPago} opciones={FORMA_PAGO} onChange={setFormasPago} conTodas={false} />
        {formasPago.includes('transferencia') && (
          <div className="grid grid--2" style={{ marginTop: '0.7rem' }}>
            <div className={clase('cbu')} {...marca('cbu')}>
              <label>CBU (número) {OBLIGATORIO}</label>
              <input type="text" value={datos.cbu || ''} onChange={setInput('cbu')} />
              {error('cbu')}
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
          <div className={clase('contacto_nombre')}>
            <label>Nombre de contacto</label>
            <input type="text" value={datos.contacto_nombre || ''} onChange={setInput('contacto_nombre')} />
          </div>
          <div className={clase('contacto_telefono')}>
            <label>Teléfono</label>
            <input type="text" value={datos.contacto_telefono || ''} onChange={setInput('contacto_telefono')} />
          </div>
          <div className={clase('contacto_mail')}>
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
          <div className={clase('solicitado_por')} {...marca('solicitado_por')}>
            <label>Nombre y apellido de quien solicita {OBLIGATORIO}</label>
            <input type="text" value={datos.solicitado_por || ''} onChange={setInput('solicitado_por')} />
            {error('solicitado_por')}
          </div>
        </div>
      </div>
    </>
  )
}
