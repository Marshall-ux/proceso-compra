import { useEffect, useState } from 'react'
import { LISTAS, fmtMoney } from '../constants.js'
import { candidatosAviso } from '../services/api.js'

// A quién se le manda el mail de "gasto para autorizar". Quien carga la solicitud
// tiene que elegir al menos uno: sin esto el aviso le llegaría a toda la planilla.
// La lista sale del servidor según la marca y el monto (solo quien puede firmarlo).
export default function SelectorAvisados({ marcas, monto, valores = [], onChange }) {
  const [candidatos, setCandidatos] = useState([])
  const [cargando, setCargando] = useState(false)
  const clave = `${(marcas || []).join('|')}#${Number(monto) || 0}`

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
          // Si cambió la marca o el monto, se descarta a quien ya no puede firmar.
          const validos = new Set(lista.filter((c) => c.tiene_mail).map((c) => c.id))
          const filtrados = valores.filter((id) => validos.has(id))
          if (filtrados.length !== valores.length) onChange(filtrados)
        })
        .catch(() => vigente && setCandidatos([]))
        .finally(() => vigente && setCargando(false))
    }, 350)
    return () => { vigente = false; clearTimeout(t) }
  }, [clave])  // eslint-disable-line react-hooks/exhaustive-deps

  const alternar = (id) =>
    onChange(valores.includes(id) ? valores.filter((x) => x !== id) : [...valores, id])

  return (
    <div className="seccion">
      <div className="seccion__titulo">
        ¿A quién le avisamos? <span style={{ color: 'var(--danger)' }}>*</span>
      </div>
      {!(marcas || []).length || !(Number(monto) > 0) ? (
        <div className="field__nota">
          Elegí la marca y cargá el monto para ver quién puede autorizar este gasto.
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
              const activa = valores.includes(c.id)
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
                    type="checkbox" name="avisar_a" checked={activa}
                    disabled={!c.tiene_mail} onChange={() => alternar(c.id)}
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
            Le llega un mail solo a quien tildes. Aparecen únicamente quienes pueden autorizar
            esta marca por este monto.
          </div>
        </>
      )}
    </div>
  )
}
