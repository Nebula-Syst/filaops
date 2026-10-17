/**
 * PrintFlow: pedidos servidos desde stock, ajuste de unidades en la ficha y
 * pedidos entregados en la lista.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, it, expect, vi } from 'vitest'
import OrderWorkflowPanel from '../../components/orders/OrderWorkflowPanel'
import SalesOrderCard from '../../components/orders/SalesOrderCard'
import StockAdjuster from '../StockAdjuster'

const renderPanel = ({ order, productionOrders = [], stockCoverage, onUseStock = vi.fn(), released = false }) => {
  render(
    <MemoryRouter>
      <OrderWorkflowPanel
        order={{ id: 5, order_number: 'SO-5', payment_status: 'pending', delivery_method: 'local_delivery', ...order }}
        orderInvoice={null}
        paymentSummary={{ total_paid: 0 }}
        productionOrders={productionOrders}
        materialRequirements={[]}
        hasOrderProduct={() => true}
        hasMainProductWO={() => released}
        hasShipmentEvidence={() => false}
        isBillingReleaseSatisfied={() => false}
        getProductionComplete={() => false}
        getProductionReleaseBlockReason={() => 'Create/send an invoice or record payment before production release'}
        stockCoverage={stockCoverage}
        onUseStock={onUseStock}
        onDeliverOrder={vi.fn()}
      />
    </MemoryRouter>
  )
  return onUseStock
}

describe('OrderWorkflowPanel — stock de producto terminado', () => {
  it('con stock suficiente ofrece servirlo sin orden de trabajo ni factura', () => {
    const onUseStock = renderPanel({
      order: { status: 'confirmed' },
      stockCoverage: { can_reserve: true, stock_covers_all: true, fully_covered: false, from_stock: 8, to_make: 0, lines: [] },
    })
    expect(screen.getByText('In stock')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create Work Orders' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Use stock' }))
    expect(onUseStock).toHaveBeenCalled()
  })

  it('servido desde stock: producción hecha y se puede entregar', () => {
    renderPanel({
      order: { status: 'ready_to_ship' },
      released: true,
      stockCoverage: { can_reserve: false, stock_covers_all: false, fully_covered: true, from_stock: 0, to_make: 0, lines: [] },
    })
    expect(screen.getByText('From stock')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark as Delivered' })).toBeInTheDocument()
  })

  it('stock parcial: explica cuánto sale del stock y cuánto se fabrica', () => {
    renderPanel({
      order: { status: 'confirmed' },
      stockCoverage: { can_reserve: true, stock_covers_all: false, fully_covered: false, from_stock: 3, to_make: 5, lines: [] },
    })
    expect(screen.getByText(/3 from stock, 5 to make\./)).toBeInTheDocument()
  })
})

describe('SalesOrderCard — pedidos entregados', () => {
  const base = { id: 1, order_number: 'SO-1', customer_name: 'Cliente', total: 10, fulfillment: { state: 'shipped', lines_ready: 1, lines_total: 1, fulfillment_percent: 100 } }

  it('entrega en mano → "Delivered"', () => {
    render(<SalesOrderCard order={{ ...base, status: 'delivered', delivery_method: 'local_delivery' }} onViewDetails={vi.fn()} />)
    expect(screen.getByText('Delivered')).toBeInTheDocument()
  })

  it('recogida → "Picked Up"', () => {
    render(<SalesOrderCard order={{ ...base, status: 'delivered', delivery_method: 'pickup' }} onViewDetails={vi.fn()} />)
    expect(screen.getByText('Picked Up')).toBeInTheDocument()
  })
})

describe('StockAdjuster', () => {
  afterEach(() => vi.restoreAllMocks())

  it('quita unidades con el ajuste de inventario', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ previous_quantity: 11, new_quantity: 9, available_quantity: 9 }),
    })
    const onAdjusted = vi.fn()
    render(<StockAdjuster item={{ id: 1, unit: 'EA', on_hand_qty: '11.0', available_qty: '11.0' }} onAdjusted={onAdjusted} />)

    fireEvent.click(screen.getByRole('button', { name: 'Remove units' }))
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '2' } })
    expect(screen.getByText('Stock after the change: 9 EA')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: 'Remove units' }).at(-1))

    await waitFor(() => expect(onAdjusted).toHaveBeenCalled())
    const url = fetchMock.mock.calls[0][0]
    expect(url).toContain('/api/v1/inventory/adjust-quantity?')
    expect(url).toContain('new_on_hand_quantity=9')
    expect(url).toContain('product_id=1')
    expect(screen.getByText('Stock updated: 11 → 9')).toBeInTheDocument()
  })

  it('no deja quitar más de lo que hay', () => {
    render(<StockAdjuster item={{ id: 1, unit: 'EA', on_hand_qty: '3' }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Remove units' }))
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '5' } })
    expect(screen.getByText('There are only 3 EA in stock.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Remove units' }).at(-1)).toBeDisabled()
  })
})
