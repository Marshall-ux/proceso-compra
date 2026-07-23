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

// Sube uno o varios PDF y devuelve una sola orden combinada.
export const extraerFacturas = (archivos) => {
  const form = new FormData()
  for (const a of archivos) form.append('archivos', a)
  return pedir('/facturas/extraer', { method: 'POST', body: form })
}

export const subirCbu = (archivo) => {
  const form = new FormData()
  form.append('archivo', archivo)
  return pedir('/archivos/cbu', { method: 'POST', body: form })
}

export const subirLegajo = (archivo) => {
  const form = new FormData()
  form.append('archivo', archivo)
  return pedir('/archivos/legajo', { method: 'POST', body: form })
}

// --- acciones de administración: van firmadas con la clave admin de la sesión ---
export const claveAdmin = () => sessionStorage.getItem('claveAdmin') || ''
const adminHeaders = () => ({ 'X-Admin-Password': claveAdmin() })

export const verificarClaveAdmin = (clave) =>
  pedir('/admin/verificar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clave }),
  })

export const blanquearPin = (autorizadoId) =>
  pedir(`/autorizados/${autorizadoId}/pin`, { method: 'DELETE', headers: adminHeaders() })

export const generarCodigoAlta = (autorizadoId) =>
  pedir(`/autorizados/${autorizadoId}/codigo-alta`, { method: 'POST', headers: adminHeaders() })

export const desbloquearAutorizado = (autorizadoId) =>
  pedir(`/autorizados/${autorizadoId}/desbloquear`, { method: 'POST', headers: adminHeaders() })

// Alta de PIN (con código de administración) o cambio (con el PIN actual).
export const definirPin = (autorizadoId, payload) =>
  pedir(`/autorizados/${autorizadoId}/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

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

export const autorizarLote = (payload) =>
  pedir('/solicitudes/autorizar-lote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

export const marcarAutopack = (id, ok) =>
  pedir(`/solicitudes/${id}/autopack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok }),
  })

export const urlPdf = (id) => `${BASE}/solicitudes/${id}/pdf`
export const urlPdfCompleto = (id) => `${BASE}/solicitudes/${id}/pdf-completo`
export const urlZip = (id) => `${BASE}/solicitudes/${id}/zip`
export const urlZipLote = (ids) => `${BASE}/solicitudes/zip?ids=${ids.join(',')}`
export const urlFactura = (id, facturaId) => `${BASE}/solicitudes/${id}/facturas/${facturaId}`
export const urlCbuImagen = (id) => `${BASE}/solicitudes/${id}/cbu-imagen`
export const urlLegajo = (id) => `${BASE}/solicitudes/${id}/legajo`
