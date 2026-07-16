// En dev Vite proxea /api al backend; en producción nginx sirve todo bajo /proceso-compra.
const BASE = import.meta.env.DEV ? '/api' : '/proceso-compra/api'

async function pedir(url, opciones = {}) {
  const res = await fetch(`${BASE}${url}`, opciones)
  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  if (!res.ok) {
    const error = new Error(data?.error || `Error ${res.status}`)
    error.status = res.status
    error.data = data
    throw error
  }
  return data
}

export const extraerFactura = (archivo) => {
  const form = new FormData()
  form.append('archivo', archivo)
  return pedir('/facturas/extraer', { method: 'POST', body: form })
}

export const listarSolicitudes = (params = {}) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
  return pedir(`/solicitudes${qs ? `?${qs}` : ''}`)
}

export const obtenerSolicitud = (id) => pedir(`/solicitudes/${id}`)

export const crearSolicitud = (datos) =>
  pedir('/solicitudes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos),
  })

export const actualizarSolicitud = (id, datos) =>
  pedir(`/solicitudes/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos),
  })

export const eliminarSolicitud = (id) => pedir(`/solicitudes/${id}`, { method: 'DELETE' })

export const autorizar = (id, payload) =>
  pedir(`/solicitudes/${id}/autorizar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

export const quitarAutorizacion = (id, autorizacionId) =>
  pedir(`/solicitudes/${id}/autorizaciones/${autorizacionId}`, { method: 'DELETE' })

export const listarAutorizados = (lista) =>
  pedir(`/autorizados${lista ? `?lista=${lista}` : ''}`)

export const urlPdf = (id) => `${BASE}/solicitudes/${id}/pdf`
export const urlFactura = (id) => `${BASE}/solicitudes/${id}/factura`
