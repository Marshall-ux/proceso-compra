import { useState } from 'react'

// Ventanas propias para confirmar o pedir un dato, en lugar de confirm() y prompt() del
// navegador (que no se pueden estilar, cortan el texto y en algunos navegadores se
// bloquean). Uso:
//   const { confirmar, pedirTexto, ventana } = useVentana()
//   if (!(await confirmar({ titulo, mensaje, aceptar: 'Eliminar', peligro: true }))) return
//   const mail = await pedirTexto({ titulo, mensaje, etiqueta, valor })   // null si cancela
//   ... y en el JSX: {ventana}
export function useVentana() {
  const [pedido, setPedido] = useState(null)   // { titulo, mensaje, aceptar, peligro, etiqueta?, valor?, resolver }
  const [texto, setTexto] = useState('')

  const abrir = (opciones) => new Promise((resolver) => {
    setTexto(opciones.valor ?? '')
    setPedido({ ...opciones, resolver })
  })
  const cerrar = (resultado) => {
    pedido?.resolver(resultado)
    setPedido(null)
  }
  const aceptar = () => cerrar(pedido.etiqueta !== undefined ? texto : true)
  const cancelar = () => cerrar(pedido.etiqueta !== undefined ? null : false)

  const ventana = pedido && (
    <div className="modal-fondo" onClick={cancelar}>
      <form className="modal" onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => { e.preventDefault(); aceptar() }}>
        <div className="card__title" style={{ marginBottom: '0.3rem' }}>{pedido.titulo}</div>
        {pedido.mensaje && <p className="card__hint">{pedido.mensaje}</p>}
        {pedido.etiqueta !== undefined && (
          <div className="field">
            <label>{pedido.etiqueta}</label>
            <input type="text" autoFocus value={texto} onChange={(e) => setTexto(e.target.value)} />
          </div>
        )}
        <div className="toolbar" style={{ marginBottom: 0, marginTop: '0.9rem' }}>
          <button type="button" className="btn btn--ghost" onClick={cancelar}>Cancelar</button>
          <button type="submit" autoFocus={pedido.etiqueta === undefined}
                  className={pedido.peligro ? 'btn btn--danger-solid' : 'btn btn--primary'}>
            {pedido.aceptar || 'Aceptar'}
          </button>
        </div>
      </form>
    </div>
  )

  return {
    confirmar: (opciones) => abrir(opciones),
    pedirTexto: (opciones) => abrir({ ...opciones, etiqueta: opciones.etiqueta ?? '' }),
    ventana,
  }
}
