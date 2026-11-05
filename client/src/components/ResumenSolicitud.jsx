import {
  CONCEPTOS, CONDICION_PAGO, CRITICIDAD, FORMA_PAGO, PROVEEDOR_TIPO, TIPO_ORDEN, UBICACIONES,
  fmtFechaHora, fmtImporte, fmtMoney,
} from '../constants.js'

const etiqueta = (opciones, valor) => opciones.find((o) => o.valor === valor)?.etiqueta || valor

// Lo que se va a firmar, en pantalla y legible en el celular. Antes los datos solo se
// veían en el PDF embebido, que en muchos celulares no se muestra: quien firmaba desde
// el mail autorizaba sin ver el gasto.
export default function ResumenSolicitud({ solicitud: s }) {
  const marcas = (s.marcas || []).map((m) => (m === 'OTRO' ? s.marca_otro || 'Otro' : m))
  const formas = (s.forma_pago || '').split(',').filter(Boolean).map((f) => etiqueta(FORMA_PAGO, f))
  const condicion = s.condicion_pago === 'cuenta_corriente' && s.condicion_dias
    ? `Cuenta corriente a ${s.condicion_dias} días`
    : s.condicion_pago === 'otras' ? s.condicion_otras || 'Otras' : etiqueta(CONDICION_PAGO, s.condicion_pago)
  const contacto = [s.contacto_nombre, s.contacto_telefono, s.contacto_mail].filter(Boolean).join(' · ')

  const datos = [
    ['Proveedor', <>
      <strong>{s.proveedor_nombre || '—'}</strong>
      <div className="resumen__extra">
        {[s.cuit && `CUIT ${s.cuit}`, etiqueta(PROVEEDOR_TIPO, s.proveedor_tipo)].filter(Boolean).join(' · ')}
      </div>
    </>],
    ['Concepto', s.concepto === 'otros' ? s.concepto_otro || 'Otros' : etiqueta(CONCEPTOS, s.concepto)],
    ['Empresa', (s.empresas || []).join(', ')],
    ['Marca y ubicación', [marcas.join(', '), etiqueta(UBICACIONES, s.ubicacion)].filter(Boolean).join(' · ')],
    ['Tipo de orden', s.tipo_orden === 'abierta' && s.duracion_orden
      ? `Abierta · ${s.duracion_orden}` : etiqueta(TIPO_ORDEN, s.tipo_orden)],
    ['Criticidad', s.criticidad === 'otro' ? s.criticidad_obs || 'Otro' : etiqueta(CRITICIDAD, s.criticidad)],
    ['Pago', [formas.join(', '), condicion].filter(Boolean).join(' · ')],
    ['Factura', [s.fecha, s.factura_numero && `N° ${s.factura_numero}`].filter(Boolean).join(' · ')],
    ['Contacto', contacto],
    ['Pedido por', [s.solicitado_por, s.created_at && `cargada el ${fmtFechaHora(s.created_at)}`]
      .filter(Boolean).join(' · ')],
  ].filter(([, valor]) => valor)

  return (
    <div className="resumen">
      <div className="resumen__monto">
        <span className="resumen__lab">Monto (IVA incluido)</span>
        <strong>{fmtImporte(s.monto_total, s.moneda)}</strong>
        {s.moneda === 'USD' && (
          <span className="resumen__extra">TC {fmtMoney(s.tipo_cambio)} = $ {fmtMoney(s.monto_pesos)}</span>
        )}
      </div>

      <dl className="resumen__datos">
        {datos.map(([lab, valor]) => (
          <div key={lab} className="resumen__dato">
            <dt className="resumen__lab">{lab}</dt>
            <dd>{valor}</dd>
          </div>
        ))}
      </dl>

      {s.observaciones && (
        <div className="resumen__dato" style={{ marginTop: '0.9rem' }}>
          <div className="resumen__lab">Observaciones</div>
          <div style={{ whiteSpace: 'pre-wrap' }}>{s.observaciones}</div>
        </div>
      )}

      {(s.items || []).length > 0 && (
        <div className="table-wrap" style={{ marginTop: '1rem' }}>
          <table className="data">
            <thead>
              <tr><th>Detalle</th><th className="num">Cant.</th><th className="num">Total</th></tr>
            </thead>
            <tbody>
              {s.items.map((it) => (
                <tr key={it.id}>
                  <td>{it.descripcion}</td>
                  <td className="num">{Number(it.cantidad) || ''}</td>
                  <td className="num">{fmtMoney(it.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
