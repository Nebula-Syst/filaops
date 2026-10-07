/**
 * PrintFlow: una petición opcional que da 404 no debe mostrar el aviso
 * "No se ha encontrado el recurso solicitado" (quietStatuses).
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApiClient } from '../apiClient'
import { on } from '../events'

const notFound = () =>
  Promise.resolve({
    ok: false,
    status: 404,
    json: () => Promise.resolve({ detail: 'No active routing found for product' }),
  })

describe('apiClient quietStatuses', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sin quietStatuses, un 404 avisa a la app', async () => {
    vi.stubGlobal('fetch', vi.fn(notFound))
    const seen = vi.fn()
    const off = on('api:error', seen)
    const client = createApiClient({ baseUrl: '' })
    await expect(client.get('/x')).rejects.toThrow()
    off()
    expect(seen).toHaveBeenCalledTimes(1)
  })

  it('con quietStatuses [404], falla sin aviso global', async () => {
    vi.stubGlobal('fetch', vi.fn(notFound))
    const seen = vi.fn()
    const off = on('api:error', seen)
    const client = createApiClient({ baseUrl: '' })
    await expect(client.get('/x', { quietStatuses: [404] })).rejects.toThrow()
    off()
    expect(seen).not.toHaveBeenCalled()
  })
})
