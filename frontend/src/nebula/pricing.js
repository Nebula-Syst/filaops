/**
 * PrintFlow: precio según la cantidad, igual que nebula_pricing en el backend.
 *
 * pricing = { units_per_bed, tiers: [{ min_quantity, unit_price }] }
 * (de GET /items/nebula/pricing). Por debajo del primer tramo vale el precio
 * de venta normal.
 *
 * - Sin piezas por cama: precio del tramo más alto que alcanza la cantidad.
 * - Con piezas por cama: camas llenas + una con el resto; cada cama cobra por
 *   pieza el tramo de las piezas que lleva (Nazareno 4 por cama: 5 uds =
 *   4×25 + 1×39).
 */
const unitFor = (base, tiers, quantity) => {
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
};

/** [{ quantity, unit_price, full }] — una parte, o camas llenas + resto. */
export function priceBreakdown(product, pricing, quantity) {
  const base = parseFloat(product?.selling_price) || 0;
  const tiers = Array.isArray(pricing) ? pricing : pricing?.tiers;
  const perBed = Array.isArray(pricing) ? null : pricing?.units_per_bed;
  if (!perBed || !Number.isInteger(quantity) || quantity <= 0) {
    return [{ quantity, unit_price: unitFor(base, tiers, quantity), full: null }];
  }
  const fullBeds = Math.floor(quantity / perBed);
  const rest = quantity - fullBeds * perBed;
  const parts = [];
  if (fullBeds) parts.push({ quantity: fullBeds * perBed, unit_price: unitFor(base, tiers, perBed), full: true, beds: fullBeds });
  if (rest) parts.push({ quantity: rest, unit_price: unitFor(base, tiers, rest), full: false, beds: 1 });
  return parts;
}

export const totalFor = (product, pricing, quantity) =>
  priceBreakdown(product, pricing, quantity).reduce((sum, p) => sum + p.quantity * p.unit_price, 0);

/** Precio por unidad (medio, si va por camas). */
export function tierPrice(product, pricing, quantity) {
  if (!quantity) return unitFor(parseFloat(product?.selling_price) || 0, Array.isArray(pricing) ? pricing : pricing?.tiers, 1);
  return totalFor(product, pricing, quantity) / quantity;
}

/** "4 × 25.00 + 1 × 39.00 (4 per bed)" para la línea del pedido; null sin camas. */
export function bedHint(product, pricing, quantity) {
  const perBed = Array.isArray(pricing) ? null : pricing?.units_per_bed;
  if (!perBed) return null;
  const parts = priceBreakdown(product, pricing, quantity);
  return `${parts.map((p) => `${p.quantity} × ${p.unit_price.toFixed(2)}`).join(" + ")} (${perBed} per bed)`;
}
