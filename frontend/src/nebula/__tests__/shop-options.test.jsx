/**
 * PrintFlow: tamaños, caja y envío de las tiendas online.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, it, expect, vi } from 'vitest'
import ShopOptions from '../ShopOptions'
import ShopSettings from '../ShopSettings'
import ShopColors from '../ShopColors'

const json = (data, ok = true) => Promise.resolve({ ok, json: () => Promise.resolve(data) })

afterEach(() => {
  vi.restoreAllMocks()
})

const boxes = [{ id: 50, sku: 'CAJA-1', name: 'Caja 10x10', cost: 0.75 }]
const goods = { items: [
  { id: 1, sku: 'NAV-HEAD', name: 'Bola de Navidad 2D' },
  { id: 2, sku: 'NAV-001', name: 'Bola 2D Pequeña' },
  { id: 3, sku: 'NAV-002', name: 'Bola 2D Grande' },
] }

describe('ShopOptions', () => {
  it('guarda los tamaños y la caja de cada uno', async () => {
    const options = { group: null, size_label: null, box_id: null, box_cost: 0, sizes: [], boxes }
    const saved = {
      ...options,
      sizes: [{ id: 2, sku: 'NAV-001', name: 'Bola 2D Pequeña', size_label: '6 cm', selling_price: 4, active: true, box_id: null }],
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, init = {}) => {
      if (String(url).includes('/api/v1/items?')) return json(goods)
      if (url.endsWith('/1/shop-sizes')) return json(saved)
      if (url.endsWith('/2/shop-box')) return json({})
      if (url.endsWith('/1/shop-options')) {
        return json(init.method === 'GET' && fetchMock.mock.calls.some(([u]) => u.endsWith('/2/shop-box'))
          ? { ...saved, sizes: [{ ...saved.sizes[0], box_id: 50 }] }
          : options)
      }
      return json({}, false)
    })

    render(<ShopOptions item={{ id: 1 }} />)
    fireEvent.click(await screen.findByText('Add size'))
    await waitFor(() => expect(screen.getByRole('option', { name: 'Bola 2D Pequeña (NAV-001)' })).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Item'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Size name'), { target: { value: ' 6 cm ' } })
    fireEvent.change(screen.getAllByRole('combobox')[2], { target: { value: '50' } })
    fireEvent.click(screen.getByText('Save sizes'))

    await screen.findByText('Saved. The shop will update in a few minutes.')
    const sizesCall = fetchMock.mock.calls.find(([u]) => u.endsWith('/1/shop-sizes'))
    expect(JSON.parse(sizesCall[1].body)).toEqual({ sizes: [{ product_id: 2, size_label: '6 cm' }] })
    const boxCall = fetchMock.mock.calls.find(([u]) => u.endsWith('/2/shop-box'))
    expect(JSON.parse(boxCall[1].body)).toEqual({ box_id: 50 })
  })

  it('un tamaño solo muestra su producto y su caja', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (String(url).includes('/api/v1/items?')) return json(goods)
      return json({ group: { id: 1, sku: 'NAV-HEAD', name: 'Bola de Navidad 2D' }, size_label: '6 cm', box_id: null, box_cost: 0, sizes: [], boxes })
    })
    render(<ShopOptions item={{ id: 2 }} />)
    expect(await screen.findByText('Bola de Navidad 2D')).toBeTruthy()
    expect(screen.queryByText('Add size')).toBeNull()
  })

  it('enseña el error del servidor', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (String(url).includes('/api/v1/items?')) return json(goods)
      if (url.endsWith('/shop-sizes')) return json({ detail: '«Bola 2D Pequeña» ya es un tamaño de «Otra»' }, false)
      return json({ group: null, size_label: null, box_id: null, box_cost: 0, sizes: [], boxes: [] })
    })
    render(<ShopOptions item={{ id: 1 }} />)
    fireEvent.click(await screen.findByText('Add size'))
    await waitFor(() => expect(screen.getByRole('option', { name: 'Bola 2D Pequeña (NAV-001)' })).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Item'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Size name'), { target: { value: 'M' } })
    fireEvent.click(screen.getByText('Save sizes'))
    expect(await screen.findByText('«Bola 2D Pequeña» ya es un tamaño de «Otra»')).toBeTruthy()
  })
})

describe('ShopOptions — personalización', () => {
  it('guarda qué elige el cliente', async () => {
    const options = { group: null, size_label: null, box_id: null, box_cost: 0, customization: 'none', sizes: [], boxes: [] }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, init = {}) => {
      if (String(url).includes('/api/v1/items?')) return json(goods)
      if (url.endsWith('/1/shop-customization')) return json({ ...options, customization: JSON.parse(init.body).customization })
      return json(options)
    })
    render(<ShopOptions item={{ id: 1 }} />)
    const select = await screen.findByLabelText('What the customer chooses')
    fireEvent.change(select, { target: { value: 'describe' } })
    await screen.findByText('Saved. The shop will update in a few minutes.')
    const call = fetchMock.mock.calls.find(([u]) => u.endsWith('/1/shop-customization'))
    expect(JSON.parse(call[1].body)).toEqual({ customization: 'describe' })
    expect(screen.getByLabelText('What the customer chooses').value).toBe('describe')
  })
})

describe('ShopColors', () => {
  it('una fila por color y guarda el nombre de la tienda', async () => {
    const colors = [
      { material_id: 10, color_id: 1, name: 'Black', color_name: 'Black', hex: '#000000', hex_secondary: null, material: 'Pla', brands: ['Elegoo'], remaining_g: 800, hidden: false },
      { material_id: 11, color_id: 1, name: 'Black', color_name: 'Black', hex: '#000000', hex_secondary: null, material: 'Abs', brands: ['Elegoo'], remaining_g: 1000, hidden: false },
    ]
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, init = {}) =>
      json(init.method === 'PUT' ? { color_id: 1, shop_name: 'Negro', hidden: false } : { colors })
    )
    render(<ShopColors />)
    const inputs = await screen.findAllByLabelText('Name in the shop')
    expect(inputs).toHaveLength(1)
    expect(screen.getByText('Pla, Abs · Elegoo · 1800 g')).toBeTruthy()
    fireEvent.change(inputs[0], { target: { value: 'Negro' } })
    fireEvent.blur(inputs[0])
    await waitFor(() => expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'PUT')).toBe(true))
    const put = fetchMock.mock.calls.find(([, i]) => i?.method === 'PUT')
    expect(put[0]).toMatch(/shop-colors\/1$/)
    expect(JSON.parse(put[1].body)).toEqual({ shop_name: 'Negro', hidden: false })
  })
})

describe('ShopSettings', () => {
  it('guarda el precio del envío a domicilio', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, init = {}) =>
      json({ home_shipping_price: init.method === 'PUT' ? 5.95 : 0 })
    )
    render(<ShopSettings />)
    const input = await screen.findByLabelText('Home delivery price')
    fireEvent.change(input, { target: { value: '5.95' } })
    fireEvent.click(screen.getByText('Save'))
    await screen.findByText('Saved. The shop will update in a few minutes.')
    const put = fetchMock.mock.calls.find(([, i]) => i?.method === 'PUT')
    expect(JSON.parse(put[1].body)).toEqual({ home_shipping_price: 5.95 })
  })
})
