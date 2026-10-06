/**
 * PrintFlow: método de entrega — envío, entrega en mano o recogida.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import DeliveryMethodSelect from '../DeliveryMethodSelect'
import { deliverActionLabel, deliveryMethodLabel, needsShipping } from '../delivery'
import OrderWorkflowPanel from '../../components/orders/OrderWorkflowPanel'

describe('delivery helpers', () => {
  it('solo el envío necesita transportista; sin método cuenta como envío', () => {
    expect(needsShipping({ delivery_method: 'ship' })).toBe(true)
    expect(needsShipping({})).toBe(true)
    expect(needsShipping(null)).toBe(true)
    expect(needsShipping('local_delivery')).toBe(false)
    expect(needsShipping({ delivery_method: 'pickup' })).toBe(false)
  })

  it('etiquetas y botón según el método', () => {
    expect(deliveryMethodLabel('pickup')).toBe('Customer pickup')
    expect(deliverActionLabel({ delivery_method: 'pickup' })).toBe('Mark as Picked Up')
    expect(deliverActionLabel('local_delivery')).toBe('Mark as Delivered')
    expect(deliverActionLabel({})).toBe('Ship Order')
  })
})

describe('DeliveryMethodSelect', () => {
  it('marca el método actual y avisa al elegir otro', () => {
    const onChange = vi.fn()
    render(<DeliveryMethodSelect value="ship" onChange={onChange} />)
    expect(screen.getByRole('radio', { name: /Carrier shipping/ })).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(screen.getByRole('radio', { name: /Customer pickup/ }))
    expect(onChange).toHaveBeenCalledWith('pickup')
  })
})

const renderPanel = (order, onDeliverOrder = vi.fn()) => {
  render(
    <MemoryRouter>
      <OrderWorkflowPanel
        order={{ id: 7, order_number: 'SO-7', payment_status: 'paid', ...order }}
        orderInvoice={null}
        paymentSummary={{ total_paid: 10 }}
        productionOrders={[{ id: 1, status: 'complete' }]}
        materialRequirements={[]}
        hasOrderProduct={() => true}
        hasMainProductWO={() => true}
        hasShipmentEvidence={() => false}
        isBillingReleaseSatisfied={() => true}
        getProductionComplete={() => true}
        getProductionReleaseBlockReason={() => ''}
        onDeliverOrder={onDeliverOrder}
      />
    </MemoryRouter>
  )
  return onDeliverOrder
}

describe('OrderWorkflowPanel — paso de entrega', () => {
  it('recogida: botón "Mark as Picked Up" sin pasar por envíos', () => {
    const onDeliver = renderPanel({ status: 'ready_to_ship', delivery_method: 'pickup' })
    expect(screen.getByText('Ready for pickup')).toBeInTheDocument()
    expect(screen.queryByText('Ship Order')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Mark as Picked Up' }))
    expect(onDeliver).toHaveBeenCalled()
  })

  it('entrega en mano: botón "Mark as Delivered"', () => {
    renderPanel({ status: 'ready_to_ship', delivery_method: 'local_delivery' })
    expect(screen.getByRole('button', { name: 'Mark as Delivered' })).toBeInTheDocument()
  })

  it('envío: sigue mostrando "Ship Order"', () => {
    renderPanel({ status: 'ready_to_ship', delivery_method: 'ship' })
    expect(screen.getByRole('button', { name: 'Ship Order' })).toBeInTheDocument()
  })
})
