import { beforeEach, describe, expect, it } from 'vitest'

describe('cartStore', () => {
  beforeEach(async () => {
    const { useCartStore } = await import('./cartStore')
    useCartStore.setState({ items: [], pricingMode: 'retail' })
  })

  it('defaults to retail pricing and reprices existing items when switched to wholesale', async () => {
    const { useCartStore } = await import('./cartStore')

    useCartStore.getState().addItem(
      {
        id: 1,
        name: 'Amoxicillin',
        sku: 'AMOX-250',
        selling_price: 80,
        wholesale_price: 75,
        total_stock: 20,
      },
      2
    )

    expect(useCartStore.getState().pricingMode).toBe('retail')
    expect(useCartStore.getState().items[0].unit_price).toBe(80)
    expect(useCartStore.getState().items[0].total_price).toBe(160)

    useCartStore.getState().setPricingMode('wholesale')

    expect(useCartStore.getState().pricingMode).toBe('wholesale')
    expect(useCartStore.getState().items[0].unit_price).toBe(75)
    expect(useCartStore.getState().items[0].total_price).toBe(150)
  })

  it('blocks wholesale mode if a cart item has no wholesale price', async () => {
    const { useCartStore } = await import('./cartStore')

    useCartStore.getState().addItem(
      {
        id: 1,
        name: 'Cetirizine',
        sku: 'CET-010',
        selling_price: 25,
        wholesale_price: null,
        total_stock: 15,
      },
      1
    )

    expect(() => useCartStore.getState().setPricingMode('wholesale')).toThrow(
      'Wholesale price is not set for Cetirizine'
    )
    expect(useCartStore.getState().pricingMode).toBe('retail')
  })
})
