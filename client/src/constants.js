// Opciones tal como figuran en el formulario F 8.4-01 Rev.07.
export const EMPRESAS = [
  'ALCO ROSARIO S.A.', 'NEOSTAR S.A.', 'XINOXIA S.A.', 'DASEOS S.A.', 'HIKARI S.A.',
]

export const MARCAS = [
  'FCA', 'HONDA', 'KIA', 'NISSAN', 'SUZUKI', 'SUBARU', 'BYD',
  'SHOWROOM FUNES', 'CAÑADA DE GOMEZ', 'OTRO',
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

// El formulario tiene 6 renglones en el detalle.
export const MAX_ITEMS = 6

export const LISTAS = {
  nissan: 'Nissan',
  jeep: 'Jeep / Chrysler',
  kia: 'Kia',
  multimarca: 'Multimarca',
}

export const fmtMoney = (v) =>
  (Number(v) || 0).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// '2026-07-16 14:01:37' -> '16/07/2026 14:01'
export const fmtFechaHora = (v) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/.exec(String(v || ''))
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}` : String(v || '')
}
