"""PrintFlow: método de entrega del pedido (sales_orders.delivery_method).

FilaOps da por hecho que todo pedido se envía con transportista a una dirección.
En PrintFlow el pedido también se puede entregar en mano o recoger en el taller:

- ``ship``: envío con transportista (comportamiento original). Exige dirección.
- ``local_delivery``: lo entrega el propio taller. Dirección opcional, sin
  transportista ni número de seguimiento.
- ``pickup``: el cliente lo recoge. Sin dirección, transportista ni seguimiento.

Al entregar un pedido sin envío se descuenta el inventario y se registra el
coste igual que en un envío (ship_order), pero el pedido pasa directamente a
"delivered".
"""
from typing import Literal, Optional

DeliveryMethod = Literal["ship", "local_delivery", "pickup"]

SHIP = "ship"
LOCAL_DELIVERY = "local_delivery"
PICKUP = "pickup"

DELIVERY_METHODS = (SHIP, LOCAL_DELIVERY, PICKUP)

# Texto para el historial del pedido (la capa i18n del frontend lo traduce).
DELIVERY_EVENT_TITLES = {
    LOCAL_DELIVERY: "Order delivered in person",
    PICKUP: "Order picked up by customer",
}


def requires_shipping(delivery_method: Optional[str]) -> bool:
    """True si el pedido va con transportista (y por tanto necesita dirección).

    NULL cuenta como envío: es el comportamiento de los pedidos anteriores a la
    columna.
    """
    return (delivery_method or SHIP) == SHIP
