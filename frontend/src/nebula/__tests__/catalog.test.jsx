/**
 * PrintFlow: precios por cantidad, archivos 3MF e importación de artículos.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, it, expect, vi } from 'vitest'
import PriceTiersEditor from '../PriceTiersEditor'
import ProductFiles from '../ProductFiles'
import ImportItemsModal from '../ImportItemsModal'
import { tierPrice } from '../pricing'

const json = (data, ok = true) => Promise.resolve({ ok, json: () => Promise.resolve(data) })

afterEach(() => {
  vi.restoreAllMocks()
})

describe('tierPrice', () => {
  const product = { selling_price: '6.00' }
  const tiers = [
    { min_quantity: 4, unit_price: 4.5 },
    { min_quantity: 200, unit_price: 2 },
  ]
  it('usa el tramo más alto que alcanza la cantidad', () => {
    expect(tierPrice(product, tiers, 1)).toBe(6)
    expect(tierPrice(product, tiers, 3)).toBe(6)
    expect(tierPrice(product, tiers, 4)).toBe(4.5)
    expect(tierPrice(product, tiers, 250)).toBe(2)
    expect(tierPrice(product, undefined, 10)).toBe(6)
  })
})

describe('PriceTiersEditor', () => {
  it('carga los tramos, añade uno y los guarda', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, opts) => {
      if (opts?.method === 'PUT') {
        const body = JSON.parse(opts.body)
        return json({ tiers: body.tiers })
      }
      return json({ base_price: 6, tiers: [{ min_quantity: 4, unit_price: 4.5, label: '4 por cama' }] })
    })
    render(<PriceTiersEditor item={{ id: 7, selling_price: '6.00' }} />)

    expect(await screen.findByDisplayValue('4 por cama')).toBeInTheDocument()
    expect(screen.getByText(/1 – 3 units/)).toBeInTheDocument()

    fireEvent.click(screen.getByText('+ Add tier'))
    const prices = screen.getAllByLabelText('Price per unit')
    fireEvent.change(prices[1], { target: { value: '2' } })
    fireEvent.click(screen.getByText('Save prices'))

    await screen.findByText('Quantity prices saved')
    const put = fetchMock.mock.calls.find(([, o]) => o?.method === 'PUT')
    expect(put[0]).toContain('/api/v1/items/7/price-tiers')
    expect(JSON.parse(put[1].body).tiers).toEqual([
      { min_quantity: 4, unit_price: 4.5, label: '4 por cama' },
      { min_quantity: 8, unit_price: 2, label: null },
    ])
  })

  it('no deja guardar cantidades repetidas', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ tiers: [{ min_quantity: 4, unit_price: 4.5 }] }))
    render(<PriceTiersEditor item={{ id: 7, selling_price: '6' }} />)
    await screen.findByDisplayValue('4.5')
    fireEvent.click(screen.getByText('+ Add tier'))
    fireEvent.change(screen.getAllByLabelText('From (units)')[1], { target: { value: '4' } })
    fireEvent.change(screen.getAllByLabelText('Price per unit')[1], { target: { value: '3' } })
    expect(screen.getAllByText('Repeated quantity').length).toBeGreaterThan(0)
    expect(screen.getByText('Save prices')).toBeDisabled()
  })
})

describe('ProductFiles', () => {
  it('lista los archivos con enlace de descarga y deja borrarlos', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, opts) => {
      if (opts?.method === 'DELETE') return json({ deleted: 1 })
      return json([
        { id: 1, file_name: 'placa 1.3mf', file_size: 2 * 1024 * 1024, notes: 'PLA blanco', download_url: '/api/v1/items/7/files/1/download' },
        { id: 2, file_name: 'placa 2.3mf', file_size: 1024, notes: null, download_url: '/api/v1/items/7/files/2/download' },
      ])
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<ProductFiles item={{ id: 7 }} />)

    const link = await screen.findByText('placa 1.3mf')
    expect(link.getAttribute('href')).toContain('/api/v1/items/7/files/1/download')
    expect(screen.getByText('2.0 MB · PLA blanco')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Delete placa 1.3mf'))
    await waitFor(() => expect(screen.queryByText('placa 1.3mf')).not.toBeInTheDocument())
    expect(fetchMock.mock.calls.some(([u, o]) => o?.method === 'DELETE' && u.endsWith('/items/7/files/1'))).toBe(true)
  })

  it('sube varios archivos a la vez', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json([]))
    const sent = []
    class FakeXHR {
      constructor() {
        this.upload = {}
      }
      open(method, url) {
        this.url = url
      }
      send(form) {
        sent.push({ url: this.url, names: form.getAll('files').map((f) => f.name) })
        this.status = 201
        this.responseText = JSON.stringify([
          { id: 3, file_name: 'a.3mf', file_size: 3, download_url: '/x/3' },
          { id: 4, file_name: 'b.3mf', file_size: 3, download_url: '/x/4' },
        ])
        this.onload()
      }
    }
    vi.stubGlobal('XMLHttpRequest', FakeXHR)
    render(<ProductFiles item={{ id: 7 }} />)
    await screen.findByText('No print files yet.')

    fireEvent.change(screen.getByTestId('product-files-input'), {
      target: { files: [new File(['abc'], 'a.3mf'), new File(['abc'], 'b.3mf')] },
    })
    expect(await screen.findByText('b.3mf')).toBeInTheDocument()
    expect(sent).toEqual([{ url: expect.stringContaining('/api/v1/items/7/files'), names: ['a.3mf', 'b.3mf'] }])
    vi.unstubAllGlobals()
  })
})

describe('ImportItemsModal', () => {
  it('sube el CSV y muestra el resumen', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      json({ created: 2, updated: 0, skipped: 1, tiers_updated: 2, errors: [{ row: 4, error: 'Falta el SKU' }] })
    )
    const onImported = vi.fn()
    render(<ImportItemsModal isOpen onClose={vi.fn()} onImported={onImported} />)

    fireEvent.change(screen.getByTestId('import-file-input'), {
      target: { files: [new File(['sku;nombre'], 'articulos.csv', { type: 'text/csv' })] },
    })
    fireEvent.click(screen.getByLabelText('Update items that already exist (same SKU)'))
    fireEvent.click(screen.getByRole('button', { name: 'Import' }))

    expect(await screen.findByText('Created: 2 · Updated: 0 · Skipped: 1')).toBeInTheDocument()
    expect(screen.getByText('Quantity prices saved for 2 items')).toBeInTheDocument()
    expect(onImported).toHaveBeenCalled()
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/items/nebula/import?update_existing=true')
  })
})

describe('precio por camas', () => {
  const product = { selling_price: '39' }
  const pricing = {
    units_per_bed: 4,
    tiers: [
      { min_quantity: 2, unit_price: 30 },
      { min_quantity: 3, unit_price: 27 },
      { min_quantity: 4, unit_price: 25 },
    ],
  }
  it('reparte en camas llenas y una con el resto', async () => {
    const { totalFor, priceBreakdown, bedHint } = await import('../pricing')
    expect([1, 2, 3, 4, 5, 7, 8, 10].map((q) => totalFor(product, pricing, q))).toEqual([39, 60, 81, 100, 139, 181, 200, 260])
    expect(priceBreakdown(product, pricing, 5).map((p) => [p.quantity, p.unit_price])).toEqual([[4, 25], [1, 39]])
    expect(bedHint(product, pricing, 7)).toBe('4 × 25.00 + 3 × 27.00 (4 per bed)')
    expect(tierPrice(product, pricing, 5)).toBeCloseTo(27.8)
  })

  it('el editor guarda las piezas por cama y enseña ejemplos', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, opts) => {
      if (opts?.method === 'PUT') {
        const body = JSON.parse(opts.body)
        return json({ units_per_bed: body.units_per_bed, tiers: body.tiers })
      }
      return json({ base_price: 39, units_per_bed: null, tiers: pricing.tiers })
    })
    render(<PriceTiersEditor item={{ id: 1, selling_price: '39' }} />)
    await screen.findAllByDisplayValue('30')
    fireEvent.change(screen.getByLabelText(/Pieces per bed/), { target: { value: '4' } })
    expect(screen.getByText(/Bed with 1:/)).toBeInTheDocument()
    expect(screen.getByText(/Order of 5:/).textContent).toMatch(/139/)
    fireEvent.click(screen.getByText('Save prices'))
    await screen.findByText('Quantity prices saved')
    const put = fetchMock.mock.calls.find(([, o]) => o?.method === 'PUT')
    expect(JSON.parse(put[1].body).units_per_bed).toBe(4)
  })
})
