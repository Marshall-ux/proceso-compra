import { MAX_ITEMS, fmtMoney } from '../constants.js'

// Detalle del servicio o producto. El total de cada renglon se recalcula solo.
export default function ItemsEditor({ items, onChange }) {
  const actualizar = (i, campo, valor) => {
    const copia = items.map((it, idx) => {
      if (idx !== i) return it
      const item = { ...it, [campo]: valor }
      if (campo === 'precio' || campo === 'cantidad') {
        item.total = (Number(item.precio) || 0) * (Number(item.cantidad) || 0)
      }
      return item
    })
    onChange(copia)
  }

  const agregar = () => onChange([...items, { descripcion: '', precio: 0, cantidad: 1, total: 0 }])
  const quitar = (i) => onChange(items.filter((_, idx) => idx !== i))

  const suma = items.reduce((acc, it) => acc + (Number(it.total) || 0), 0)
  const deMas = items.length - MAX_ITEMS

  return (
    <>
      {deMas > 0 && (
        <div className="alert alert--warning">
          El formulario oficial tiene {MAX_ITEMS} renglones y cargaste {items.length}.
          {' '}Los últimos {deMas} no van a entrar en el PDF: agrupalos en un renglón
          {' '}(por ejemplo «Varios según factura») o detallalos en observaciones.
        </div>
      )}
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Descripción</th>
              <th style={{ width: 130 }}>Precio</th>
              <th style={{ width: 90 }}>Cant.</th>
              <th style={{ width: 140 }}>Total</th>
              <th style={{ width: 44 }} />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr><td colSpan={5} style={{ color: 'var(--text-muted)' }}>Sin renglones cargados.</td></tr>
            )}
            {items.map((item, i) => (
              <tr key={i} className={i >= MAX_ITEMS ? 'row--review' : undefined}>
                <td>
                  <input
                    className="cell-input"
                    value={item.descripcion || ''}
                    placeholder="Descripción"
                    onChange={(e) => actualizar(i, 'descripcion', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    className="cell-input cell-input--num"
                    type="number" step="0.01"
                    value={item.precio ?? ''}
                    onChange={(e) => actualizar(i, 'precio', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    className="cell-input cell-input--num"
                    type="number" step="0.01"
                    value={item.cantidad ?? ''}
                    onChange={(e) => actualizar(i, 'cantidad', e.target.value)}
                  />
                </td>
                <td className="num">{fmtMoney(item.total)}</td>
                <td>
                  <button type="button" className="btn btn--danger" onClick={() => quitar(i)} title="Quitar">
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="toolbar" style={{ marginTop: '0.9rem', marginBottom: 0 }}>
        <button type="button" className="btn btn--ghost btn--sm" onClick={agregar}>+ Agregar renglón</button>
        <span className="toolbar__info">Suma de renglones: <strong>$ {fmtMoney(suma)}</strong></span>
      </div>
    </>
  )
}
