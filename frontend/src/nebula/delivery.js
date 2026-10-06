/**
 * PrintFlow: método de entrega del pedido (sales_orders.delivery_method).
 *
 * - ship: envío con transportista (lo de FilaOps). Exige dirección.
 * - local_delivery: lo entrega el taller. Dirección opcional, sin transportista.
 * - pickup: lo recoge el cliente. Sin dirección ni transportista.
 *
 * Los textos están en inglés como el resto de la interfaz; la capa i18n los
 * traduce (locales/es.json).
 */
export const DELIVERY_METHODS = [
  { value: "ship", label: "Carrier shipping", hint: "Needs an address and a carrier" },
  { value: "local_delivery", label: "Hand delivery", hint: "You deliver it yourself" },
  { value: "pickup", label: "Customer pickup", hint: "The customer collects it" },
];

const methodOf = (orderOrMethod) =>
  (typeof orderOrMethod === "string" ? orderOrMethod : orderOrMethod?.delivery_method) || "ship";

/** True si el pedido va con transportista (y por tanto necesita dirección). */
export const needsShipping = (orderOrMethod) => methodOf(orderOrMethod) === "ship";

export const deliveryMethodLabel = (orderOrMethod) =>
  DELIVERY_METHODS.find((m) => m.value === methodOf(orderOrMethod))?.label || "Carrier shipping";

/** Texto del botón que da salida al pedido. */
export const deliverActionLabel = (orderOrMethod) => {
  const method = methodOf(orderOrMethod);
  if (method === "pickup") return "Mark as Picked Up";
  if (method === "local_delivery") return "Mark as Delivered";
  return "Ship Order";
};
