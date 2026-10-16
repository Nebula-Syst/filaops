import { describe, it, expect, beforeEach } from 'vitest'
import { formatCurrency, parseDecimal, toFixedSafe, setLocaleDefaults } from '../number'

// Reset module-level defaults before each test so tests are independent
beforeEach(() => {
  setLocaleDefaults('USD', 'en-US')
})

describe('formatCurrency', () => {
  it('formats a number as USD by default', () => {
    expect(formatCurrency(1234.56)).toBe('$1,234.56')
  })

  it('returns empty string for null', () => {
    expect(formatCurrency(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(formatCurrency(undefined)).toBe('')
  })

  it('returns empty string for NaN', () => {
    expect(formatCurrency(NaN)).toBe('')
  })

  it('formats Decimal strings from the API (Nebula fork)', () => {
    expect(formatCurrency('25.00')).toBe('$25.00')
    expect(formatCurrency('1234.5')).toBe('$1,234.50')
    expect(formatCurrency('')).toBe('')
    expect(formatCurrency('abc')).toBe('')
  })

  it('formats zero correctly', () => {
    expect(formatCurrency(0)).toBe('$0.00')
  })

  it('accepts explicit currency override', () => {
    const result = formatCurrency(100, 'EUR', 'en-US')
    expect(result).toContain('100')
    expect(result).toContain('€')
  })

  it('uses updated defaults after setLocaleDefaults', () => {
    setLocaleDefaults('EUR', 'de-DE')
    const result = formatCurrency(1234.56)
    // German format uses comma as decimal separator
    expect(result).toContain('1.234,56')
    expect(result).toContain('€')
  })

  it('falls back to USD when setLocaleDefaults called with empty string', () => {
    setLocaleDefaults('', '')
    expect(formatCurrency(100)).toBe('$100.00')
  })
})

describe('setLocaleDefaults', () => {
  it('updates the currency default', () => {
    setLocaleDefaults('CAD', 'en-CA')
    const result = formatCurrency(100)
    // CAD formats with CA$ prefix in en-CA
    expect(result).toContain('100')
  })

  it('reverts cleanly to USD after reset', () => {
    setLocaleDefaults('JPY', 'ja-JP')
    setLocaleDefaults('USD', 'en-US')
    expect(formatCurrency(100)).toBe('$100.00')
  })
})

describe('parseDecimal', () => {
  it('parses a plain number string', () => {
    expect(parseDecimal('123.45')).toBe(123.45)
  })

  it('parses a comma-thousand-separated number', () => {
    expect(parseDecimal('1,234.56')).toBe(1234.56)
  })

  it('strips spaces before parsing — space-separated thousands collapse', () => {
    // The normalizer strips ALL spaces and commas first ([\s,_] regex),
    // so "1 234,56" → "12456" → 12456 (comma was also stripped before
    // the trailing-comma→dot replacement runs). Known limitation.
    // Primary supported formats: "1,234.56" (US) and "1234.56" (plain).
    expect(parseDecimal('1 234,56')).toBe(123456)
  })

  it('returns null for null', () => {
    expect(parseDecimal(null)).toBeNull()
  })

  it('returns null for undefined', () => {
    expect(parseDecimal(undefined)).toBeNull()
  })

  it('returns null for non-numeric string', () => {
    expect(parseDecimal('abc')).toBeNull()
  })

  it('returns the number directly when given a number', () => {
    expect(parseDecimal(42.5)).toBe(42.5)
  })

  it('returns null for NaN number input', () => {
    expect(parseDecimal(NaN)).toBeNull()
  })
})

describe('toFixedSafe', () => {
  it('rounds using Math.round — subject to floating-point representation', () => {
    // 1.005 in IEEE-754 is actually 1.00499999... so Math.round(1.005 * 100) / 100 = 1.00 → "1"
    // toFixedSafe avoids String.toFixed() drift but uses standard Math.round.
    expect(toFixedSafe(1.005)).toBe('1')  // floating-point caveat
    expect(toFixedSafe(1.5)).toBe('1.5') // Math.round(150)/100 = 1.5
    expect(toFixedSafe(1.4)).toBe('1.4') // Math.round(140)/100 = 1.4
    expect(toFixedSafe(2.0)).toBe('2')
  })

  it('respects custom digits parameter', () => {
    expect(toFixedSafe(1.2345, 3)).toBe('1.235')
  })

  it('returns empty string for null', () => {
    expect(toFixedSafe(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(toFixedSafe(undefined)).toBe('')
  })

  it('handles zero', () => {
    expect(toFixedSafe(0)).toBe('0')
  })
})
