// Opciones tal como figuran en el formulario F 8.4-01 Rev.07.
export const EMPRESAS = [
  'ALCO ROSARIO S.A.', 'NEOSTAR S.A.', 'XINOXIA S.A.', 'DASEOS S.A.', 'HIKARI S.A.',
]

export const MARCAS = [
  'FCA', 'HONDA', 'KIA', 'NISSAN', 'SUZUKI', 'SUBARU', 'BYD',
  'SHOWROOM FUNES', 'CAÑADA DE GOMEZ', 'OTRO',
]

// Sede del gasto. No está en el formulario de papel: con la razón social define a qué
// cajera le llega el aviso cuando la solicitud queda autorizada.
export const UBICACIONES = [
  { valor: 'rosario', etiqueta: 'Rosario' },
  { valor: 'santa_fe', etiqueta: 'Santa Fe' },
]

export const CONCEPTOS = [
  { valor: 'publicidad', etiqueta: 'Publicidad / Marketing' },
  { valor: 'muebles', etiqueta: 'Muebles y útiles' },
  { valor: 'gastos', etiqueta: 'Gastos generales' },
  { valor: 'reparacion', etiqueta: 'Reparación y mantenimiento' },
  { valor: 'comisiones', etiqueta: 'Comisiones y/o honorarios' },
  { valor: 'otros', etiqueta: 'Otros' },
]

export const PROVEEDOR_TIPO = [
  { valor: 'habitual', etiqueta: 'Proveedor habitual' },
  { valor: 'nuevo', etiqueta: 'Nuevo proveedor' },
]

export const TIPO_ORDEN = [
  { valor: 'cerrada', etiqueta: 'Orden cerrada' },
  { valor: 'abierta', etiqueta: 'Orden abierta' },
]

export const FORMA_PAGO = [
  { valor: 'efectivo', etiqueta: 'Efectivo' },
  { valor: 'cheque', etiqueta: 'Cheque' },
  { valor: 'echeq', etiqueta: 'E-cheq' },
  { valor: 'transferencia', etiqueta: 'Transferencia' },
]

export const CONDICION_PAGO = [
  { valor: 'contado', etiqueta: 'Contado' },
  { valor: 'cuenta_corriente', etiqueta: 'Cuenta corriente' },
  { valor: 'otras', etiqueta: 'Otras' },
]

export const CONDICION_DIAS = ['7', '20', '30']

export const CRITICIDAD = [
  { valor: 'urgente', etiqueta: 'Urgente' },
  { valor: 'informado', etiqueta: 'Informado en factura' },
  { valor: 'otro', etiqueta: 'Otro' },
]

export const REQUIERE_OC = [
  { valor: 'si', etiqueta: 'Sí' },
  { valor: 'no', etiqueta: 'No' },
]

export const MONEDAS = [
  { valor: 'ARS', etiqueta: 'Pesos ($)' },
  { valor: 'USD', etiqueta: 'Dólares (U$S)' },
]

// Las solicitudes viejas no tienen moneda: son en pesos.
export const simboloMoneda = (moneda) => (moneda === 'USD' ? 'U$S' : '$')

// 1234.5, 'USD' -> 'U$S 1.234,50'
export const fmtImporte = (v, moneda) => `${simboloMoneda(moneda)} ${fmtMoney(v)}`

// Equivalente en pesos (los topes de los autorizantes están en pesos). En dólares sin
// tipo de cambio da 0: todavía no se puede comparar.
export const montoEnPesos = (monto, moneda, tipoCambio) =>
  (Number(monto) || 0) * (moneda === 'USD' ? (Number(tipoCambio) || 0) : 1)

// El formulario tiene 6 renglones en el detalle.
export const MAX_ITEMS = 6

export const LISTAS = {
  nissan: 'Nissan',
  jeep: 'Jeep / Chrysler',
  jeep_byd: 'Jeep / Chrysler + BYD',
  kia: 'Kia',
  honda: 'Honda',
  byd: 'BYD',
  multimarca: 'Multimarca',
}

export const fmtMoney = (v) =>
  (Number(v) || 0).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// Cuánto hace que espera una solicitud cargada en `creada` ('2026-11-05 14:01:37'):
// { texto: 'desde hoy' | 'desde ayer' | 'hace 3 días', demorada }. Demorada a partir de
// las 48 h, que es cuando sale el primer recordatorio.
export const esperaDesde = (creada) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(String(creada || ''))
  if (!m) return { texto: '', demorada: false }
  const desde = new Date(m[1], m[2] - 1, m[3], m[4], m[5])
  const hoy = new Date()
  const dias = Math.round((new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate())
    - new Date(desde.getFullYear(), desde.getMonth(), desde.getDate())) / 864e5)
  const texto = dias <= 0 ? 'desde hoy' : dias === 1 ? 'desde ayer' : `hace ${dias} días`
  return { texto, demorada: hoy - desde >= 48 * 36e5 }
}

// '2026-07-16 14:01:37' -> '16/07/2026 14:01'
export const fmtFechaHora = (v) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/.exec(String(v || ''))
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}` : String(v || '')
}
