/**
 * PrintFlow: bobinas por taller y enlaces de la tienda.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, it, expect, vi } from 'vitest'
import SpoolsByWorkshop from '../SpoolsByWorkshop'
import ShopLinks from '../ShopLinks'
import { formatGrams, matchesSearch } from '../spools'

const json = (data, ok = true) => Promise.resolve({ ok, json: () => Promise.resolve(data) })

afterEach(() => {
  vi.restoreAllMocks()
})

const summary = {
  brands: ['Elegoo'],
  locations: [
    {
      location_id: 1,
      location_name: 'GL Printworks Pedrera',
      count: 2,
      total_g: 1000,
      items: [
        {
          brand: 'Elegoo',
          product_id: 5,
          sku: 'MAT-PLA-BLACK',
          name: 'PLA - Black',
          material: 'Pla',
          color: 'Black',
          color_hex: '#000000',
          count: 2,
          total_g: 1000,
          spools: [
            { id: 11, spool_number: 'BOB-00001', current_g: 100, initial_g: 1000, status: 'active' },
            { id: 12, spool_number: 'BOB-00002', current_g: 900, initial_g: 1000, status: 'active' },
          ],
        },
      ],
    },
  ],
}

describe('spools helpers', () => {
  it('formatea gramos y kilos', () => {
    expect(formatGrams(100)).toBe('100 g')
    expect(formatGrams(1000)).toBe('1 kg')
    expect(formatGrams(1250)).toBe('1,25 kg')
  })
  it('busca colores en español', () => {
    expect(matchesSearch('PLA - Black', 'negro')).toBe(true)
    expect(matchesSearch('PLA - Black', 'pla negro')).toBe(true)
    expect(matchesSearch('PLA - Grey', 'gris')).toBe(true)
    expect(matchesSearch('PLA - Green', 'gris')).toBe(false)
    expect(matchesSearch('PETG - Black', 'pla negro')).toBe(false)
  })
})

describe('SpoolsByWorkshop', () => {
  it('agrupa por marca y color y da de alta varias bobinas', async () => {
    const onChanged = vi.fn()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, opts) => {
      if (url.endsWith('/spools/nebula/summary')) return json(summary)
      if (url.endsWith('/spools/nebula/materials'))
        return json([
          { product_id: 5, sku: 'MAT-PLA-BLACK', name: 'PLA - Black', color: 'Black', material: 'Pla' },
          { product_id: 6, sku: 'MAT-PLA-WHITE', name: 'PLA - White', color: 'White', material: 'Pla' },
        ])
      if (opts?.method === 'POST') return json({ created: [{ id: 13 }] })
      return json({})
    })
    render(<SpoolsByWorkshop locations={[{ id: 1, name: 'GL Printworks Pedrera' }]} onChanged={onChanged} />)

    expect(await screen.findByText('GL Printworks Pedrera')).toBeInTheDocument()
    expect(screen.getByText('Elegoo ·')).toBeInTheDocument()
    expect(screen.getByText('100 g')).toBeInTheDocument()
    expect(screen.getByText('900 g')).toBeInTheDocument()
    expect(screen.getAllByText('2 spools')).toHaveLength(2)

    fireEvent.click(screen.getByRole('button', { name: 'Add spools' }))
    fireEvent.change(screen.getByPlaceholderText('Elegoo, Bambu Lab…'), { target: { value: 'Elegoo' } })
    fireEvent.change(screen.getByPlaceholderText('Search: black, PLA, PETG…'), { target: { value: 'negro' } })
    const select = await screen.findByRole('listbox', { name: 'Filament' })
    await waitFor(() => expect(select.querySelectorAll('option')).toHaveLength(1))
    fireEvent.change(select, { target: { value: '5' } })
    fireEvent.change(screen.getByLabelText('How many'), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    const post = fetchMock.mock.calls.find(([, o]) => o?.method === 'POST')
    expect(JSON.parse(post[1].body)).toEqual({
      product_id: 5,
      brand: 'Elegoo',
      location_id: 1,
      initial_g: 1000,
      current_g: null,
      quantity: 3,
    })
  })

  it('corrige lo que le queda a una bobina', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((_url, opts) =>
      opts?.method === 'PATCH' ? json({}) : json(summary),
    )
    render(<SpoolsByWorkshop locations={[]} />)
    fireEvent.click(await screen.findByText('100 g'))
    fireEvent.change(screen.getByLabelText('Remaining grams BOB-00001'), { target: { value: '40' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, o]) => o?.method === 'PATCH')
      expect(patch[0]).toMatch(/\/api\/v1\/spools\/11$/)
      expect(JSON.parse(patch[1].body)).toEqual({ current_weight_g: 40, reason: 'Pesada' })
    })
  })
})

const STORES = [
  { id: 'sc_gl', name: 'GL Printworks', domains: ['glprintworks.com'], selected: false },
  { id: 'sc_al', name: 'Los Aliados', domains: ['losaliados.glprintworks.com'], selected: true },
]
const LINK = 'https://losaliados.glprintworks.com/es/products/nazareno'

const shopFetch = (stores = STORES) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation((url, opts) => {
    if (opts?.method === 'PUT') {
      const ids = JSON.parse(opts.body).store_ids
      return json({ stores: stores.map((s) => ({ ...s, selected: ids.includes(s.id) })) })
    }
    if (String(url).endsWith('/shops')) return json({ stores })
    return json([{ store: 'Los Aliados', url: LINK }])
  })

describe('ShopLinks', () => {
  it('enseña las tiendas marcadas y el enlace de la tienda', async () => {
    shopFetch()
    render(<ShopLinks item={{ id: 7 }} />)
    const link = await screen.findByText(LINK)
    expect(link).toHaveAttribute('href', LINK)
    expect(screen.getByLabelText(/Los Aliados/)).toBeChecked()
    expect(screen.getByLabelText(/GL Printworks/)).not.toBeChecked()
  })

  it('guarda al marcar una tienda', async () => {
    const fetchMock = shopFetch()
    render(<ShopLinks item={{ id: 7 }} />)
    fireEvent.click(await screen.findByLabelText(/GL Printworks/))
    await waitFor(() => {
      const put = fetchMock.mock.calls.find(([, o]) => o?.method === 'PUT')
      expect(put[0]).toMatch(/\/api\/v1\/items\/7\/shops$/)
      expect(JSON.parse(put[1].body)).toEqual({ store_ids: ['sc_gl', 'sc_al'] })
    })
    expect(await screen.findByText(/The shop will update/)).toBeInTheDocument()
    expect(screen.getByLabelText(/GL Printworks/)).toBeChecked()
  })

  it('no pinta nada si aún no hay tiendas', async () => {
    const fetchMock = shopFetch([])
    const { container } = render(<ShopLinks item={{ id: 7 }} />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
