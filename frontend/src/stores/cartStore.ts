/**
 * Shopping cart state management for POS.
 */
import { create } from 'zustand'

export type PricingMode = 'retail' | 'wholesale'

interface CartProductInput {
  id: number
  name: string
  sku: string
  selling_price: number
  wholesale_price?: number | null
  total_stock: number
}

interface CartItem {
  product_id: number
  name: string
  sku: string
  quantity: number
  unit_price: number
  retail_price: number
  wholesale_price: number | null
  discount_amount: number
  total_price: number
  available_stock: number
}

interface CartState {
  items: CartItem[]
  pricingMode: PricingMode
  setPricingMode: (mode: PricingMode) => void
  addItem: (product: CartProductInput, quantity: number) => void
  updateQuantity: (productId: number, quantity: number) => void
  updateDiscount: (productId: number, discount: number) => void
  removeItem: (productId: number) => void
  clearCart: () => void
  getSubtotal: () => number
  getTotalItems: () => number
}

function resolveUnitPrice(
  product: CartProductInput | CartItem,
  pricingMode: PricingMode
) {
  if (pricingMode === 'wholesale') {
    if (product.wholesale_price == null) {
      throw new Error(`Wholesale price is not set for ${product.name}`)
    }
    return product.wholesale_price
  }

  return 'selling_price' in product ? product.selling_price : product.retail_price
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],
  pricingMode: 'retail',

  setPricingMode: (pricingMode) => {
    const repricedItems = get().items.map((item) => {
      const unitPrice = resolveUnitPrice(item, pricingMode)
      return {
        ...item,
        unit_price: unitPrice,
        total_price: unitPrice * item.quantity - item.discount_amount,
      }
    })

    set({
      pricingMode,
      items: repricedItems,
    })
  },

  addItem: (product, quantity) => {
    const items = get().items
    const pricingMode = get().pricingMode
    const existingItem = items.find((item) => item.product_id === product.id)
    const unitPrice = resolveUnitPrice(product, pricingMode)

    if (existingItem) {
      const newQuantity = existingItem.quantity + quantity
      if (newQuantity > product.total_stock) {
        throw new Error('Insufficient stock')
      }

      set({
        items: items.map((item) =>
          item.product_id === product.id
            ? {
                ...item,
                quantity: newQuantity,
                total_price:
                  item.unit_price * newQuantity - item.discount_amount,
              }
            : item
        ),
      })
    } else {
      if (quantity > product.total_stock) {
        throw new Error('Insufficient stock')
      }

      const newItem: CartItem = {
        product_id: product.id,
        name: product.name,
        sku: product.sku,
        quantity,
        unit_price: unitPrice,
        retail_price: product.selling_price,
        wholesale_price: product.wholesale_price ?? null,
        discount_amount: 0,
        total_price: unitPrice * quantity,
        available_stock: product.total_stock,
      }

      set({ items: [...items, newItem] })
    }
  },

  updateQuantity: (productId, quantity) => {
    const items = get().items
    const item = items.find((i) => i.product_id === productId)

    if (item && quantity > item.available_stock) {
      throw new Error('Insufficient stock')
    }

    set({
      items: items.map((item) =>
        item.product_id === productId
          ? {
              ...item,
              quantity,
              total_price: item.unit_price * quantity - item.discount_amount,
            }
          : item
      ),
    })
  },

  updateDiscount: (productId, discount) => {
    set({
      items: get().items.map((item) =>
        item.product_id === productId
          ? {
              ...item,
              discount_amount: discount,
              total_price: item.unit_price * item.quantity - discount,
            }
          : item
      ),
    })
  },

  removeItem: (productId) => {
    set({
      items: get().items.filter((item) => item.product_id !== productId),
    })
  },

  clearCart: () => {
    set({ items: [], pricingMode: 'retail' })
  },

  getSubtotal: () => {
    return get().items.reduce((sum, item) => sum + item.total_price, 0)
  },

  getTotalItems: () => {
    return get().items.reduce((sum, item) => sum + item.quantity, 0)
  },
}))
