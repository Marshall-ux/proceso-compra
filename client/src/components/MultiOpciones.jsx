// Grupo de casillas de selección múltiple (como los checkbox del formulario en papel),
// con un atajo "Todas" para tildar/destildar todo de una.
export default function MultiOpciones({ nombre, valores = [], opciones, onChange }) {
  const lista = Array.isArray(valores) ? valores : []

  const alternar = (val) =>
    onChange(lista.includes(val) ? lista.filter((x) => x !== val) : [...lista, val])

  const todas = () => {
    const vals = opciones.map((o) => (typeof o === 'string' ? o : o.valor))
    onChange(lista.length === vals.length ? [] : vals)
  }

  const totalOpciones = opciones.length
  const todasActivas = lista.length === totalOpciones && totalOpciones > 0

  return (
    <div className="opciones">
      <button
        type="button"
        className={`opcion opcion--todas ${todasActivas ? 'opcion--activa' : ''}`}
        onClick={todas}
      >
        {todasActivas ? '✓ Todas' : 'Todas'}
      </button>
      {opciones.map((o) => {
        const val = typeof o === 'string' ? o : o.valor
        const etiqueta = typeof o === 'string' ? o : o.etiqueta
        const activa = lista.includes(val)
        return (
          <label key={val} className={`opcion ${activa ? 'opcion--activa' : ''}`}>
            <input type="checkbox" name={nombre} checked={activa} onChange={() => alternar(val)} />
            {etiqueta}
          </label>
        )
      })}
    </div>
  )
}
