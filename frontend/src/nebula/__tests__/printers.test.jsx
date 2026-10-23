/**
 * PrintFlow: estado en vivo de las impresoras.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, it, expect, vi } from 'vitest'
import PrintersLive from '../PrintersLive'
import { finishTime, formatDuration } from '../printers'

const json = (data, ok = true) => Promise.resolve({ ok, json: () => Promise.resolve(data) })

afterEach(() => {
  vi.restoreAllMocks()
})

const printing = {
  id: 1,
  code: 'BAM-001',
  name: 'P1S',
  model: 'P1S',
  missing: [],
  live: {
    online: true,
    status: 'printing',
    state: 'RUNNING',
    percent: 42,
    remaining_minutes: 75,
    layer: 30,
    total_layers: 120,
    file: 'Nazareno 20cm',
    print_error: null,
    hms: [],
    ams: [{ unit: 0, slot: 1, material: 'PLA', color: '#FF0000', active: true }],
    nozzles: [{ current: 219, target: 220 }],
    bed: { current: 60, target: 60 },
    chamber: null,
  },
  product: { id: 7, sku: 'SSA-001', name: 'Nazareno', production_orders: [{ id: 3, code: 'WO-0003', status: 'in_progress' }] },
}

const noCode = { id: 2, code: 'BAM-002', name: 'H2D', model: 'H2D', missing: ['access_code'], live: null, product: null }

describe('formatDuration / finishTime', () => {
  it('formatea minutos', () => {
    expect(formatDuration(75)).toBe('1 h 15 min')
    expect(formatDuration(9)).toBe('9 min')
    expect(formatDuration(0)).toBeNull()
    expect(formatDuration('x')).toBeNull()
  })
  it('añade el día si termina otro día', () => {
    const now = new Date(2026, 9, 23, 23, 0)
    expect(finishTime(30, now)).not.toMatch(/\s/)
    expect(finishTime(120, now)).toMatch(/\s/)
    expect(finishTime(null, now)).toBeNull()
  })
})

describe('PrintersLive', () => {
  it('pinta la impresión en curso y la que no tiene código', async () => {
    const onEdit = vi.fn()
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ running: true, printers: [printing, noCode] }))
    render(
      <MemoryRouter>
        <PrintersLive onEdit={onEdit} />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Nazareno 20cm')).toBeInTheDocument()
    expect(screen.getByText('42%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '42')
    expect(screen.getByText(/1 h 15 min left/)).toBeInTheDocument()
    expect(screen.getByText('WO-0003')).toHaveAttribute('href', '/admin/production/3')
    expect(screen.getByText('PLA')).toBeInTheDocument()

    expect(screen.getByText('access code')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(onEdit).toHaveBeenCalledWith(2)
  })

  it('no pinta nada sin impresoras Bambu', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ running: true, printers: [] }))
    const { container } = render(
      <MemoryRouter>
        <PrintersLive />
      </MemoryRouter>,
    )
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('avisa del código de acceso incorrecto', async () => {
    const bad = { ...noCode, missing: [], live: { online: false, connect_error: 'bad_access_code' } }
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ running: true, printers: [bad] }))
    render(
      <MemoryRouter>
        <PrintersLive />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Wrong access code.')).toBeInTheDocument()
    expect(screen.getByText('Offline')).toBeInTheDocument()
  })
})
