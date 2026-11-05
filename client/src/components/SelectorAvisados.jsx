import { useEffect, useState } from 'react'
import { LISTAS, fmtMoney } from '../constants.js'
import { candidatosAviso } from '../services/api.js'

// Quién firma la solicitud. Quien la carga tiene que elegir UNA persona, y el mail de
// "gasto para autorizar" le llega exclusivamente a ella (ni a toda la planilla ni a
// varios a la vez). La lista sale del servidor según la marca y el monto: solo quien
// puede firmarlo solo. `valores` es [id] o []: el servidor lo guarda como lista.
export default function SelectorAvisados({ marcas, monto, valores = [], onChange }) {
  const [candidatos, setCandidatos] = useState([])
  const [cargando, setCargando] = useState(false)
  const clave = `${(marcas || []).join('|')}#${Number(monto) || 0}`
  const elegido = valores[0]

  useEffect(() => {
    if (!(marcas || []).length || !(Number(monto) > 0)) {
      setCandidatos([])
      return
    }
    let vigente = true
    setCargando(true)
    // Espera a que termine de tipear el monto antes de pedir la lista.
    const t = setTimeout(() => {
      candidatosAviso(marcas, monto)
        .then((lista) => {
          if (!vigente) return
          setCandidatos(lista)
          // Si cambió la marca o el monto y el elegido ya no puede firmar, se descarta.
          const validos = new Set(lista.filter((c) => c.tiene_mail).map((c) => c.id))
          const filtrados = valores.filter((id) => validos.has(id)).slice(0, 1)
          if (filtrados.length !== valores.length) onChange(filtrados)
        })
        .catch(() => vigente && setCandidatos([]))
        .finally(() => vigente && setCargando(false))
    }, 350)
    return () => { vigente = false; clearTimeout(t) }
  }, [clave])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="seccion">
      <div className="seccion__titulo">
        ¿Quién firma esta solicitud? <span style={{ color: 'var(--danger)' }}>*</span>
      </div>
      {!(marcas || []).length || !(Number(monto) > 0) ? (
        <div className="field__nota">
          Elegí la marca y cargá el monto (en dólares, también el tipo de cambio) para ver
          quién puede autorizar este gasto.
        </div>
      ) : cargando && candidatos.length === 0 ? (
        <div className="field__nota"><span className="spinner spinner--dark" /> Buscando autorizados…</div>
      ) : candidatos.length === 0 ? (
        <div className="alert alert--warning">
          Nadie puede autorizar solo un gasto de esta marca por este monto. Revisá la marca y el monto.
        </div>
      ) : (
        <>
          <div className="opciones">
            {candidatos.map((c) => {
              const activa = elegido === c.id
              return (
                <label
                  key={c.id}
                  className={`opcion ${activa ? 'opcion--activa' : ''}`}
                  style={c.tiene_mail ? undefined : { opacity: 0.5, cursor: 'not-allowed' }}
                  title={c.tiene_mail
                    ? `${c.cargo} · ${c.sin_limite ? 'sin límite' : `hasta $ ${fmtMoney(c.monto_autorizado)}`}`
                    : 'No tiene mail cargado: pedile a administración que lo cargue'}
                >
                  <input
                    type="radio" name="avisar_a" checked={activa}
                    disabled={!c.tiene_mail} onChange={() => onChange([c.id])}
                  />
                  {c.nombre}
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {c.tiene_mail ? LISTAS[c.lista] || c.lista : 'sin mail'}
                  </span>
                </label>
              )
            })}
          </div>
          <div className="field__nota">
            Elegí una sola persona: el mail le llega únicamente a ella. Aparecen solo quienes
            pueden autorizar esta marca por este monto.
          </div>
        </>
      )}
    </div>
  )
}
