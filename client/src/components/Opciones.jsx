// Grupo de opciones excluyentes: replica los checkbox del formulario en papel.
export default function Opciones({ nombre, valor, opciones, onChange }) {
  return (
    <div className="opciones">
      {opciones.map((o) => {
        const val = typeof o === 'string' ? o : o.valor
        const etiqueta = typeof o === 'string' ? o : o.etiqueta
        const activa = valor === val
        return (
          <label key={val} className={`opcion ${activa ? 'opcion--activa' : ''}`}>
            <input
              type="radio"
              name={nombre}
              checked={activa}
              onChange={() => onChange(val)}
            />
            {etiqueta}
          </label>
        )
      })}
    </div>
  )
}
