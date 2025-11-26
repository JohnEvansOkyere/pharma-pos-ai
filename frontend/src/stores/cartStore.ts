/**
 * Shopping cart state management for POS.
 */
import { create } from 'zustand'

interface CartItem {
  product_id: number
  name: string
  sku: string
  quantity: number
  unit_price: number
  discount_amount: number
  total_price: number
  available_stock: number
}

interface CartState {
  items: CartItem[]
  addItem: (product: any, quantity: number) => void
  updateQuantity: (productId: number, quantity: number) => void
  updateDiscount: (productId: number, discount: number) => void
  removeItem: (productId: number) => void
  clearCart: () => void
  getSubtotal: () => number
  getTotalItems: () => number
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],

  addItem: (product, quantity) => {
    const items = get().items
    const existingItem = items.find((item) => item.product_id === product.id)

    if (existingItem) {
      // Update quantity
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
      // Add new item
      if (quantity > product.total_stock) {
        throw new Error('Insufficient stock')
      }

      const newItem: CartItem = {
        product_id: product.id,
        name: product.name,
        sku: product.sku,
        quantity,
        unit_price: product.selling_price,
        discount_amount: 0,
        total_price: product.selling_price * quantity,
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
    set({ items: [] })
  },

  getSubtotal: () => {
    return get().items.reduce((sum, item) => sum + item.total_price, 0)
  },

  getTotalItems: () => {
    return get().items.reduce((sum, item) => sum + item.quantity, 0)
  },
}))
