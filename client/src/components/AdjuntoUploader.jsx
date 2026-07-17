import { useRef, useState } from 'react'

// Sube un adjunto (imagen del CBU, legajo PDF) y avisa al padre con {archivo, nombre}.
// `nombre` es el nombre visible del archivo ya cargado (o vacío si todavía no hay).
export default function AdjuntoUploader({ label, hint, accept, nombre, onSubir, onListo, onQuitar }) {
  const ref = useRef(null)
  const [subiendo, setSubiendo] = useState(false)
  const [error, setError] = useState('')

  const elegir = async (archivo) => {
    if (!archivo) return
    setSubiendo(true)
    setError('')
    try {
      onListo(await onSubir(archivo))
    } catch (e) {
      setError(e.message)
    } finally {
      setSubiendo(false)
      if (ref.current) ref.current.value = ''
    }
  }

  return (
    <div className="field">
      <label>{label}</label>
      {nombre ? (
        <div className="adjunto">
          <span className="adjunto__nombre">📎 {nombre}</span>
          <button type="button" className="btn btn--danger btn--sm" onClick={onQuitar}>Quitar</button>
        </div>
      ) : (
        <>
          <button
            type="button" className="btn btn--ghost btn--sm"
            onClick={() => ref.current?.click()} disabled={subiendo}
          >
            {subiendo ? <><span className="spinner spinner--dark" /> Subiendo…</> : '📎 Elegir archivo'}
          </button>
          {hint && <div className="field__nota">{hint}</div>}
        </>
      )}
      {error && <div className="field__nota" style={{ color: 'var(--danger)' }}>{error}</div>}
      <input
        ref={ref} type="file" accept={accept} style={{ display: 'none' }}
        onChange={(e) => elegir(e.target.files?.[0])}
      />
    </div>
  )
}
