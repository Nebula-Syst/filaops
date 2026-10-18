/**
 * PrintFlow: precio unitario según la cantidad (tramos del artículo).
 *
 * tiers = [{ min_quantity, unit_price }] (de GET /items/nebula/price-tiers).
 * Por debajo del primer tramo vale el precio de venta normal. Igual que
 * nebula_pricing.price_for_quantity en el backend.
 */
export function tierPrice(product, tiers, quantity) {
  const base = parseFloat(product?.selling_price) || 0;
  let price = base;
  let best = -1;
  for (const t of tiers || []) {
    const min = parseFloat(t.min_quantity);
    if (min <= quantity && min > best) {
      best = min;
      price = parseFloat(t.unit_price);
    }
  }
  return price;
}
