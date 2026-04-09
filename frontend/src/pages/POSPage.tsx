import { useEffect, useMemo, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import {
  FiAlertTriangle,
  FiClock,
  FiCreditCard,
  FiMinus,
  FiPhone,
  FiPlus,
  FiPrinter,
  FiSearch,
  FiShoppingCart,
  FiTrash2,
  FiUser,
  FiXCircle,
} from 'react-icons/fi'

import { api } from '../services/api'
import { useCartStore } from '../stores/cartStore'
import type { PricingMode } from '../stores/cartStore'
import { useAuthStore } from '../stores/authStore'

interface Product {
  id: number
  name: string
  generic_name?: string
  sku: string
  barcode?: string
  dosage_form: string
  strength?: string
  selling_price: number
  wholesale_price?: number | null
  total_stock: number
  manufacturer?: string
  nearest_expiry?: string
}

interface ProductCatalogResponse {
  items: Product[]
  total: number
}

type ColumnFractions = {
  products: number
  cart: number
  checkout: number
}

const PRODUCT_RESULT_LIMIT = 30
const DEFAULT_COLUMN_FRACTIONS: ColumnFractions = {
  products: 0.42,
  cart: 0.33,
  checkout: 0.25,
}

function formatCurrency(value: number) {
  return `GH₵ ${value.toFixed(2)}`
}

function getExpiryState(nearestExpiry?: string) {
  if (!nearestExpiry) {
    return {
      label: 'No expiry data',
      className:
        'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
      urgency: 'none',
    }
  }

  const today = new Date()
  const expiryDate = new Date(nearestExpiry)
  const daysUntilExpiry = Math.ceil(
    (expiryDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)
  )

  if (daysUntilExpiry <= 30) {
    return {
      label: `Near expiry · ${expiryDate.toLocaleDateString('en-GB')}`,
      className: 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-300',
      urgency: 'critical',
    }
  }

  if (daysUntilExpiry <= 90) {
    return {
      label: `Watch expiry · ${expiryDate.toLocaleDateString('en-GB')}`,
      className:
        'bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300',
      urgency: 'warning',
    }
  }

  return {
    label: `Expiry · ${expiryDate.toLocaleDateString('en-GB')}`,
    className:
      'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300',
    urgency: 'normal',
  }
}

export default function POSPage() {
  const desktopLayoutRef = useRef<HTMLDivElement | null>(null)
  const resizeStateRef = useRef<{
    divider: 'products-cart' | 'cart-checkout'
    startX: number
    startFractions: ColumnFractions
  } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [catalogQuery, setCatalogQuery] = useState('')
  const [products, setProducts] = useState<Product[]>([])
  const [totalProducts, setTotalProducts] = useState(0)
  const [isLoadingProducts, setIsLoadingProducts] = useState(false)
  const [customerName, setCustomerName] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'momo'>('cash')
  const [momoNumber, setMomoNumber] = useState('')
  const [momoReference, setMomoReference] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [lastSale, setLastSale] = useState<any>(null)
  const [showPrintDialog, setShowPrintDialog] = useState(false)
  const [isDesktopLayout, setIsDesktopLayout] = useState(() =>
    typeof window !== 'undefined'
      ? window.matchMedia('(min-width: 1024px)').matches
      : false
  )
  const [columnFractions, setColumnFractions] = useState<ColumnFractions>(
    DEFAULT_COLUMN_FRACTIONS
  )

  const { user } = useAuthStore()
  const {
    items,
    pricingMode,
    setPricingMode,
    addItem,
    updateQuantity,
    removeItem,
    clearCart,
    getSubtotal,
    getTotalItems,
  } = useCartStore()
  const subtotal = getSubtotal()
  const totalItems = getTotalItems()
  const paidAmount = subtotal
  const selectedProductIds = useMemo(
    () => new Set(items.map((item) => item.product_id)),
    [items]
  )

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setCatalogQuery(searchQuery.trim())
    }, 200)

    return () => window.clearTimeout(timeoutId)
  }, [searchQuery])

  useEffect(() => {
    loadProducts(catalogQuery)
  }, [catalogQuery])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    const mediaQuery = window.matchMedia('(min-width: 1024px)')
    const handleChange = (event: MediaQueryListEvent) => {
      setIsDesktopLayout(event.matches)
    }

    setIsDesktopLayout(mediaQuery.matches)
    mediaQuery.addEventListener('change', handleChange)

    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [])

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      const resizeState = resizeStateRef.current
      const container = desktopLayoutRef.current
      if (!resizeState || !container) {
        return
      }

      const containerWidth = Math.max(container.getBoundingClientRect().width - 24, 1)
      const deltaFraction = (event.clientX - resizeState.startX) / containerWidth
      const minProducts = 300 / containerWidth
      const minCart = 280 / containerWidth
      const minCheckout = 260 / containerWidth

      if (resizeState.divider === 'products-cart') {
        const pairTotal =
          resizeState.startFractions.products + resizeState.startFractions.cart
        const nextProducts = Math.min(
          Math.max(resizeState.startFractions.products + deltaFraction, minProducts),
          pairTotal - minCart
        )

        setColumnFractions({
          products: nextProducts,
          cart: pairTotal - nextProducts,
          checkout: resizeState.startFractions.checkout,
        })
        return
      }

      const pairTotal =
        resizeState.startFractions.cart + resizeState.startFractions.checkout
      const nextCart = Math.min(
        Math.max(resizeState.startFractions.cart + deltaFraction, minCart),
        pairTotal - minCheckout
      )

      setColumnFractions({
        products: resizeState.startFractions.products,
        cart: nextCart,
        checkout: pairTotal - nextCart,
      })
    }

    const handleMouseUp = () => {
      resizeStateRef.current = null
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [])

  const loadProducts = async (query: string) => {
    setIsLoadingProducts(true)
    try {
      const response: ProductCatalogResponse = await api.getProductsCatalog({
        q: query || undefined,
        limit: PRODUCT_RESULT_LIMIT,
        skip: 0,
        is_active: true,
      })
      setProducts(response.items)
      setTotalProducts(response.total)
    } catch (error) {
      console.error('Failed to load products:', error)
      toast.error('Failed to load products')
    } finally {
      setIsLoadingProducts(false)
    }
  }

  const handleAddToCart = (product: Product) => {
    if (product.total_stock <= 0) {
      toast.error('This product is out of stock')
      return
    }

    try {
      addItem(
        {
          id: product.id,
          name: product.name,
          sku: product.sku,
          selling_price: product.selling_price,
          wholesale_price: product.wholesale_price,
          total_stock: product.total_stock,
        },
        1
      )
      toast.success(`${product.name} added to cart`)
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handlePricingModeChange = (nextMode: PricingMode) => {
    if (nextMode === pricingMode) {
      return
    }

    try {
      setPricingMode(nextMode)
      toast.success(
        nextMode === 'wholesale'
          ? 'Wholesale pricing enabled for this sale'
          : 'Retail pricing enabled for this sale'
      )
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handleQuantityChange = (productId: number, quantity: number) => {
    if (quantity < 1) {
      removeItem(productId)
      return
    }

    try {
      updateQuantity(productId, quantity)
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const resetCheckoutState = () => {
    clearCart()
    setCustomerName('')
    setCustomerPhone('')
    setMomoNumber('')
    setMomoReference('')
  }

  const handleCompleteSale = async () => {
    if (items.length === 0) {
      toast.error('Cart is empty')
      return
    }

    if (paymentMethod === 'momo' && !momoNumber.trim()) {
      toast.error('Enter MOMO number to continue')
      return
    }

    setIsProcessing(true)

    try {
      const sale = await api.createSale({
        pricing_mode: pricingMode,
        items: items.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity,
          unit_price: item.unit_price,
          discount_amount: item.discount_amount || 0,
        })),
        payment_method: paymentMethod,
        amount_paid: paidAmount,
        customer_name: customerName || undefined,
        customer_phone: customerPhone || undefined,
        momo_number: paymentMethod === 'momo' ? momoNumber : undefined,
        momo_reference: paymentMethod === 'momo' ? momoReference : undefined,
        discount_amount: 0,
        tax_amount: 0,
      })

      setLastSale(sale)
      setShowPrintDialog(true)
      toast.success(`Sale completed · ${sale.invoice_number}`)
      resetCheckoutState()
      await loadProducts(catalogQuery)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Sale failed')
    } finally {
      setIsProcessing(false)
    }
  }

  const handlePrintReceipt = () => {
    const receiptElement = document.querySelector(
      '.receipt-print-area'
    ) as HTMLElement | null
    if (receiptElement) {
      receiptElement.style.display = 'block'
    }

    window.setTimeout(() => {
      window.print()
      if (receiptElement) {
        receiptElement.style.display = 'none'
      }
      setShowPrintDialog(false)
      setLastSale(null)
    }, 100)
  }

  const beginColumnResize = (
    divider: 'products-cart' | 'cart-checkout',
    clientX: number
  ) => {
    resizeStateRef.current = {
      divider,
      startX: clientX,
      startFractions: columnFractions,
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }

  return (
    <>
      <div className="flex h-[calc(100vh-8.5rem)] min-h-[680px] flex-col gap-4 overflow-hidden print:hidden">
        <div className="card shrink-0 px-5 py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                Pharmacy POS
              </h1>
              <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500 dark:text-gray-400">
                <span className="inline-flex items-center gap-2">
                  <FiClock className="h-4 w-4" />
                  {new Date().toLocaleString('en-GB')}
                </span>
                <span>Cashier: {user?.full_name || user?.username || 'Operator'}</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 lg:min-w-[360px]">
              <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-900/50">
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Items
                </p>
                <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {items.length}
                </p>
              </div>
              <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-900/50">
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Quantity
                </p>
                <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {totalItems}
                </p>
              </div>
              <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-900/50">
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Total
                </p>
                <p className="mt-1 text-lg font-semibold text-primary-600 dark:text-primary-400">
                  {formatCurrency(subtotal)}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-end">
            <div className="flex h-[42px] w-full max-w-[280px] rounded-lg border border-gray-200 bg-gray-100 p-1 dark:border-gray-700 dark:bg-gray-800">
              <button
                type="button"
                onClick={() => handlePricingModeChange('retail')}
                className={`flex-1 rounded-md text-sm font-medium transition-colors ${
                  pricingMode === 'retail'
                    ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
                    : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                }`}
              >
                Retail
              </button>
              <button
                type="button"
                onClick={() => handlePricingModeChange('wholesale')}
                className={`flex-1 rounded-md text-sm font-medium transition-colors ${
                  pricingMode === 'wholesale'
                    ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
                    : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                }`}
              >
                Wholesale
              </button>
            </div>
          </div>
        </div>

        <div
          ref={desktopLayoutRef}
          className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:gap-0"
          style={
            isDesktopLayout
              ? {
                  gridTemplateColumns: `${columnFractions.products}fr 12px ${columnFractions.cart}fr 12px ${columnFractions.checkout}fr`,
                }
              : undefined
          }
        >
          <section className="card flex min-h-0 flex-col overflow-hidden">
            <div className="border-b border-gray-200 px-4 py-4 dark:border-gray-700">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
                    Products
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Search and add directly to the current sale.
                  </p>
                </div>
                <div className="text-right text-sm text-gray-500 dark:text-gray-400">
                  <p>{catalogQuery ? 'Matches' : 'Shown'}</p>
                  <p className="font-semibold text-gray-900 dark:text-gray-100">
                    {totalProducts}
                  </p>
                </div>
              </div>

              <div className="mt-4 flex gap-3">
                <label className="relative flex-1">
                  <FiSearch className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="input h-11 pl-10"
                    placeholder="Search by product name, generic name, SKU, or barcode"
                    autoFocus
                  />
                </label>
                {catalogQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="btn-secondary h-11 shrink-0 px-4"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {isLoadingProducts ? (
                <div className="flex h-full items-center justify-center text-gray-500 dark:text-gray-400">
                  Loading products...
                </div>
              ) : products.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center px-6 text-center text-gray-500 dark:text-gray-400">
                  <FiSearch className="mb-3 h-10 w-10" />
                  <p className="text-base font-medium text-gray-900 dark:text-gray-100">
                    No products found
                  </p>
                  <p className="mt-1 text-sm">
                    Try a different name, SKU, barcode, or generic name.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-gray-200 dark:divide-gray-700">
                  {products.map((product) => {
                    const expiryState = getExpiryState(product.nearest_expiry)
                    const isOutOfStock = product.total_stock <= 0
                    const isLowStock =
                      product.total_stock > 0 && product.total_stock <= 10
                    const alreadyInCart = selectedProductIds.has(product.id)

                    return (
                      <button
                        key={product.id}
                        type="button"
                        onClick={() => handleAddToCart(product)}
                        disabled={isOutOfStock}
                        className={`flex w-full items-center gap-3 px-4 py-3 text-left transition-colors ${
                          isOutOfStock
                            ? 'cursor-not-allowed bg-gray-50 opacity-70 dark:bg-gray-900/40'
                            : 'bg-white hover:bg-primary-50 dark:bg-gray-800 dark:hover:bg-gray-700/60'
                        }`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <p className="truncate font-medium text-gray-900 dark:text-gray-100">
                              {product.name}
                            </p>
                            {alreadyInCart && (
                              <span className="rounded-full bg-primary-50 px-2 py-0.5 text-[11px] font-medium text-primary-700 dark:bg-primary-900/20 dark:text-primary-300">
                                In cart
                              </span>
                            )}
                          </div>
                          <p className="mt-1 truncate text-xs text-gray-500 dark:text-gray-400">
                            SKU {product.sku}
                            {product.generic_name ? ` • ${product.generic_name}` : ''}
                            {product.strength ? ` • ${product.strength}` : ''}
                            {product.manufacturer ? ` • ${product.manufacturer}` : ''}
                          </p>
                        </div>

                        <div className="hidden min-w-[150px] text-xs md:block">
                          <div className="flex justify-end">
                            <span className={`rounded-full px-2.5 py-1 ${expiryState.className}`}>
                              {expiryState.label}
                            </span>
                          </div>
                        </div>

                        <div className="min-w-[126px] text-right">
                          <p className="text-base font-semibold text-primary-600 dark:text-primary-400">
                            {formatCurrency(
                              pricingMode === 'wholesale' &&
                                product.wholesale_price != null
                                ? product.wholesale_price
                                : product.selling_price
                            )}
                          </p>
                          {pricingMode === 'wholesale' &&
                            product.wholesale_price == null && (
                              <p className="mt-1 text-xs text-red-600 dark:text-red-300">
                                No wholesale price
                              </p>
                            )}
                          <p
                            className={`mt-1 text-xs ${
                              isOutOfStock
                                ? 'text-red-600 dark:text-red-300'
                                : isLowStock
                                ? 'text-amber-600 dark:text-amber-300'
                                : 'text-gray-500 dark:text-gray-400'
                            }`}
                          >
                            {isOutOfStock
                              ? 'Out of stock'
                              : `Stock ${product.total_stock}`}
                          </p>
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          </section>

          {isDesktopLayout && (
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize products and cart panels"
              className="hidden cursor-col-resize items-stretch justify-center lg:flex"
              onMouseDown={(event) =>
                beginColumnResize('products-cart', event.clientX)
              }
            >
              <div className="h-full w-1 rounded-full bg-gray-200 transition-colors hover:bg-primary-400 dark:bg-gray-700 dark:hover:bg-primary-500" />
            </div>
          )}

          <section className="card flex min-h-0 flex-col overflow-hidden">
            <div className="flex items-center justify-between border-b border-gray-200 px-4 py-4 dark:border-gray-700">
              <div>
                <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
                  Current Sale
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {items.length > 0
                    ? `${items.length} item${items.length === 1 ? '' : 's'} · ${totalItems} unit${totalItems === 1 ? '' : 's'}`
                    : 'Cart is empty'}
                </p>
              </div>
              {items.length > 0 && (
                <button
                  onClick={clearCart}
                  className="text-sm font-medium text-red-600 hover:text-red-700"
                >
                  Clear
                </button>
              )}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {items.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center px-6 text-center text-gray-500 dark:text-gray-400">
                  <FiShoppingCart className="mb-3 h-10 w-10" />
                  <p className="text-base font-medium text-gray-900 dark:text-gray-100">
                    No items added yet
                  </p>
                  <p className="mt-1 text-sm">
                    Search on the left and add products to build the sale.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-gray-200 dark:divide-gray-700">
                  {items.map((item) => (
                    <div
                      key={item.product_id}
                      className="flex items-center gap-3 px-4 py-3"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium text-gray-900 dark:text-gray-100">
                          {item.name}
                        </p>
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                          SKU {item.sku} • Unit price {formatCurrency(item.unit_price)}
                        </p>
                      </div>

                      <div className="inline-flex items-center rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-700 dark:bg-gray-800">
                        <button
                          onClick={() =>
                            handleQuantityChange(item.product_id, item.quantity - 1)
                          }
                          className="rounded-md p-2 text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                        >
                          <FiMinus className="h-4 w-4" />
                        </button>
                        <span className="min-w-[42px] text-center text-sm font-semibold text-gray-900 dark:text-gray-100">
                          {item.quantity}
                        </span>
                        <button
                          onClick={() =>
                            handleQuantityChange(item.product_id, item.quantity + 1)
                          }
                          className="rounded-md p-2 text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                        >
                          <FiPlus className="h-4 w-4" />
                        </button>
                      </div>

                      <div className="min-w-[110px] text-right">
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          Total
                        </p>
                        <p className="font-semibold text-primary-600 dark:text-primary-400">
                          {formatCurrency(item.total_price)}
                        </p>
                      </div>

                      <button
                        onClick={() => removeItem(item.product_id)}
                        className="rounded-lg p-2 text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-900/20"
                        title="Remove item"
                      >
                        <FiTrash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {isDesktopLayout && (
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize cart and checkout panels"
              className="hidden cursor-col-resize items-stretch justify-center lg:flex"
              onMouseDown={(event) =>
                beginColumnResize('cart-checkout', event.clientX)
              }
            >
              <div className="h-full w-1 rounded-full bg-gray-200 transition-colors hover:bg-primary-400 dark:bg-gray-700 dark:hover:bg-primary-500" />
            </div>
          )}

          <section className="card flex min-h-0 flex-col overflow-hidden">
            <div className="border-b border-gray-200 px-4 py-4 dark:border-gray-700">
              <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
                Checkout
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Totals stay visible while you add and edit items.
              </p>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
              <div className="space-y-4">
                <div className="rounded-lg bg-gray-900 p-4 text-white dark:bg-black">
                  <div className="flex items-center justify-between text-sm text-gray-300">
                    <span>Items</span>
                    <span>{items.length}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-sm text-gray-300">
                    <span>Quantity</span>
                    <span>{totalItems}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-sm text-gray-300">
                    <span>Subtotal</span>
                    <span>{formatCurrency(subtotal)}</span>
                  </div>
                  <div className="mt-4 border-t border-gray-700 pt-4">
                    <div className="flex items-center justify-between text-2xl font-bold">
                      <span>Total</span>
                      <span>{formatCurrency(subtotal)}</span>
                    </div>
                    <div className="mt-3 flex items-center justify-between text-sm text-gray-300">
                      <span>Pricing</span>
                      <span className="capitalize">{pricingMode}</span>
                    </div>
                    <div className="mt-3 flex items-center justify-between text-sm text-gray-300">
                      <span>Payment</span>
                      <span>{paymentMethod === 'momo' ? 'MoMo' : 'Cash'}</span>
                    </div>
                  </div>
                </div>

                <label>
                  <span className="label flex items-center gap-2">
                    <FiUser className="h-4 w-4" />
                    Customer Name
                  </span>
                  <input
                    type="text"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    className="input"
                    placeholder="Optional"
                  />
                </label>

                <label>
                  <span className="label flex items-center gap-2">
                    <FiPhone className="h-4 w-4" />
                    Customer Phone
                  </span>
                  <input
                    type="tel"
                    value={customerPhone}
                    onChange={(e) => setCustomerPhone(e.target.value)}
                    className="input"
                    placeholder="Optional"
                  />
                </label>

                <div>
                  <span className="label mb-1.5 flex items-center gap-2">
                    <FiCreditCard className="h-4 w-4" />
                    Payment Method
                  </span>
                  <div className="flex h-[42px] rounded-lg border border-gray-200 bg-gray-100 p-1 dark:border-gray-700 dark:bg-gray-800">
                    <button
                      onClick={(e) => {
                        e.preventDefault()
                        setPaymentMethod('cash')
                      }}
                      className={`flex-1 rounded-md text-sm font-medium transition-colors ${
                        paymentMethod === 'cash'
                          ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
                          : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                      }`}
                    >
                      Cash
                    </button>
                    <button
                      onClick={(e) => {
                        e.preventDefault()
                        setPaymentMethod('momo')
                      }}
                      className={`flex-1 rounded-md text-sm font-medium transition-colors ${
                        paymentMethod === 'momo'
                          ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
                          : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                      }`}
                    >
                      MoMo
                    </button>
                  </div>
                </div>

                {paymentMethod === 'momo' ? (
                  <>
                    <label>
                      <span className="label">MOMO Number</span>
                      <input
                        type="tel"
                        value={momoNumber}
                        onChange={(e) => setMomoNumber(e.target.value)}
                        className="input"
                        placeholder="0XX XXX XXXX"
                        required
                      />
                    </label>
                    <label>
                      <span className="label">MOMO Reference</span>
                      <input
                        type="text"
                        value={momoReference}
                        onChange={(e) => setMomoReference(e.target.value)}
                        className="input"
                        placeholder="Optional reference"
                      />
                    </label>
                  </>
                ) : null}

                <button
                  onClick={handleCompleteSale}
                  disabled={items.length === 0 || isProcessing}
                  className="btn-primary h-12 w-full disabled:opacity-50"
                >
                  {isProcessing
                    ? 'Processing sale...'
                    : `Complete Sale · ${formatCurrency(subtotal)}`}
                </button>
              </div>
            </div>
          </section>
        </div>

        {showPrintDialog && lastSale && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
            <div className="w-full max-w-md rounded-xl bg-white p-7 shadow-xl dark:bg-gray-800">
              <div className="text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300">
                  <FiPrinter className="h-6 w-6" />
                </div>
                <h2 className="mt-4 text-2xl font-semibold text-gray-900 dark:text-gray-100">
                  Sale completed
                </h2>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                  Invoice {lastSale.invoice_number}
                </p>
                <p className="mt-3 text-3xl font-bold text-primary-600 dark:text-primary-400">
                  {formatCurrency(lastSale.total_amount)}
                </p>
              </div>

              <div className="mt-6 grid gap-3 rounded-lg bg-gray-50 p-4 text-sm dark:bg-gray-900/40">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Payment</span>
                  <span className="font-medium capitalize text-gray-900 dark:text-gray-100">
                    {lastSale.payment_method === 'momo' ? 'Mobile Money' : 'Cash'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Paid</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">
                    {formatCurrency(lastSale.amount_paid)}
                  </span>
                </div>
              </div>

              <div className="mt-6 flex gap-3">
                <button
                  onClick={handlePrintReceipt}
                  className="btn-primary flex-1"
                >
                  Print Receipt
                </button>
                <button
                  onClick={() => {
                    setShowPrintDialog(false)
                    setLastSale(null)
                  }}
                  className="btn-secondary flex-1"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {lastSale && (
        <div className="receipt-print-area" style={{ display: 'none' }}>
          <div
            style={{
              width: '80mm',
              margin: '0 auto',
              fontFamily: 'monospace',
              fontSize: '12px',
              padding: '5mm',
              color: '#000',
              backgroundColor: '#fff',
            }}
          >
            <div
              style={{
                textAlign: 'center',
                marginBottom: '10px',
                paddingBottom: '10px',
                borderBottom: '2px dashed #000',
              }}
            >
              <h1
                style={{
                  fontSize: '18px',
                  fontWeight: 'bold',
                  margin: '0 0 3px 0',
                  color: '#000',
                }}
              >
                GYSBIN PHARMACY ANNEX
              </h1>
              <p style={{ margin: '2px 0', fontSize: '10px' }}>
                Point of Sale Receipt
              </p>
            </div>

            <div
              style={{
                marginBottom: '10px',
                fontSize: '10px',
                borderBottom: '1px dashed #000',
                paddingBottom: '8px',
              }}
            >
              <p style={{ margin: '2px 0' }}>
                Date: {new Date(lastSale.created_at).toLocaleString('en-GB')}
              </p>
              <p style={{ margin: '2px 0' }}>
                Invoice: <strong>{lastSale.invoice_number}</strong>
              </p>
              <p style={{ margin: '2px 0' }}>
                Cashier: {user?.full_name || user?.username || 'Operator'}
              </p>
              {lastSale.customer_name && (
                <p style={{ margin: '2px 0' }}>
                  Customer: {lastSale.customer_name}
                </p>
              )}
              {lastSale.customer_phone && (
                <p style={{ margin: '2px 0' }}>
                  Phone: {lastSale.customer_phone}
                </p>
              )}
            </div>

            <div style={{ marginBottom: '10px' }}>
              <table
                style={{ width: '100%', fontSize: '10px', borderCollapse: 'collapse' }}
              >
                <thead>
                  <tr style={{ borderBottom: '1px dashed #000' }}>
                    <th
                      style={{
                        textAlign: 'left',
                        paddingBottom: '5px',
                        fontWeight: 'bold',
                      }}
                    >
                      ITEM
                    </th>
                    <th
                      style={{
                        textAlign: 'center',
                        paddingBottom: '5px',
                        fontWeight: 'bold',
                        width: '15%',
                      }}
                    >
                      QTY
                    </th>
                    <th
                      style={{
                        textAlign: 'right',
                        paddingBottom: '5px',
                        fontWeight: 'bold',
                        width: '20%',
                      }}
                    >
                      PRICE
                    </th>
                    <th
                      style={{
                        textAlign: 'right',
                        paddingBottom: '5px',
                        fontWeight: 'bold',
                        width: '20%',
                      }}
                    >
                      TOTAL
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {lastSale.items.map((item: any, index: number) => (
                    <tr key={index}>
                      <td style={{ paddingTop: '5px', paddingBottom: '5px' }}>
                        {item.product_name}
                      </td>
                      <td
                        style={{
                          textAlign: 'center',
                          paddingTop: '5px',
                          paddingBottom: '5px',
                        }}
                      >
                        {item.quantity}
                      </td>
                      <td
                        style={{
                          textAlign: 'right',
                          paddingTop: '5px',
                          paddingBottom: '5px',
                        }}
                      >
                        {item.unit_price.toFixed(2)}
                      </td>
                      <td
                        style={{
                          textAlign: 'right',
                          paddingTop: '5px',
                          paddingBottom: '5px',
                        }}
                      >
                        {item.total_price.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div
              style={{
                marginBottom: '10px',
                fontSize: '11px',
                borderTop: '1px dashed #000',
                paddingTop: '8px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: '5px',
                }}
              >
                <span>Subtotal:</span>
                <span>{formatCurrency(lastSale.subtotal)}</span>
              </div>
              <div
                style={{
                  borderTop: '2px solid #000',
                  paddingTop: '8px',
                  marginTop: '8px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontWeight: 'bold',
                    fontSize: '13px',
                  }}
                >
                  <span>TOTAL:</span>
                  <span>{formatCurrency(lastSale.total_amount)}</span>
                </div>
              </div>
              <div
                style={{
                  marginTop: '10px',
                  paddingTop: '8px',
                  borderTop: '1px dashed #000',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: '3px',
                  }}
                >
                  <span>Payment:</span>
                  <span>
                    {lastSale.payment_method === 'momo' ? 'Mobile Money' : 'Cash'}
                  </span>
                </div>
                {lastSale.payment_method === 'momo' && lastSale.momo_number && (
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '9px',
                      marginBottom: '3px',
                    }}
                  >
                    <span>MOMO:</span>
                    <span>{lastSale.momo_number}</span>
                  </div>
                )}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: '3px',
                  }}
                >
                  <span>Amount Paid:</span>
                  <span>{formatCurrency(lastSale.amount_paid)}</span>
                </div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontWeight: 'bold',
                    fontSize: '12px',
                  }}
                >
                  <span>Change:</span>
                  <span>{formatCurrency(lastSale.change_amount)}</span>
                </div>
              </div>
            </div>

            <div
              style={{
                textAlign: 'center',
                marginTop: '12px',
                paddingTop: '10px',
                borderTop: '2px dashed #000',
                fontSize: '11px',
              }}
            >
              <p style={{ fontWeight: 'bold', margin: '3px 0' }}>
                Thank you for your business
              </p>
              <p style={{ margin: '3px 0' }}>Please keep this receipt for reference.</p>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
