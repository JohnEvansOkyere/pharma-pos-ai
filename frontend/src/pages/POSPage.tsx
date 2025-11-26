import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { useCartStore } from '../stores/cartStore'
import toast from 'react-hot-toast'
import { FiSearch, FiTrash2, FiShoppingCart } from 'react-icons/fi'

export default function POSPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [customerName, setCustomerName] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('cash')
  const [amountPaid, setAmountPaid] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)

  const { items, addItem, updateQuantity, removeItem, clearCart, getSubtotal } =
    useCartStore()

  useEffect(() => {
    if (searchQuery.length >= 2) {
      searchProducts()
    } else {
      setSearchResults([])
    }
  }, [searchQuery])

  const searchProducts = async () => {
    setIsSearching(true)
    try {
      const results = await api.searchProducts(searchQuery)
      setSearchResults(results)
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setIsSearching(false)
    }
  }

  const handleAddToCart = (product: any) => {
    try {
      addItem(product, 1)
      toast.success(`Added ${product.name} to cart`)
      setSearchQuery('')
      setSearchResults([])
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

  const handleCompleteSale = async () => {
    if (items.length === 0) {
      toast.error('Cart is empty')
      return
    }

    const paid = parseFloat(amountPaid)
    const total = getSubtotal()

    if (isNaN(paid) || paid < total) {
      toast.error('Invalid payment amount')
      return
    }

    setIsProcessing(true)

    try {
      const saleData = {
        items: items.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity,
          unit_price: item.unit_price,
          discount_amount: item.discount_amount,
        })),
        payment_method: paymentMethod,
        amount_paid: paid,
        customer_name: customerName || undefined,
        customer_phone: customerPhone || undefined,
        discount_amount: 0,
        tax_amount: 0,
      }

      const sale = await api.createSale(saleData)

      toast.success(
        `Sale completed! Invoice: ${sale.invoice_number}\nChange: $${sale.change_amount.toFixed(
          2
        )}`
      )

      // Clear cart and form
      clearCart()
      setCustomerName('')
      setCustomerPhone('')
      setAmountPaid('')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Sale failed')
    } finally {
      setIsProcessing(false)
    }
  }

  const subtotal = getSubtotal()
  const change = parseFloat(amountPaid) - subtotal || 0

  return (
    <div className="h-full flex flex-col lg:flex-row gap-6">
      {/* Left Panel - Product Search & Cart */}
      <div className="flex-1 flex flex-col space-y-6">
        {/* Search */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
            Search Products
          </h2>
          <div className="relative">
            <FiSearch className="absolute left-3 top-3 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10"
              placeholder="Search by name, SKU, or barcode..."
              autoFocus
            />
          </div>

          {/* Search Results */}
          {searchResults.length > 0 && (
            <div className="mt-4 space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
              {searchResults.map((product) => (
                <div
                  key={product.id}
                  onClick={() => handleAddToCart(product)}
                  className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-medium text-gray-900 dark:text-gray-100">
                        {product.name}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        SKU: {product.sku} • Stock: {product.total_stock}
                      </p>
                    </div>
                    <p className="font-semibold text-primary-600 dark:text-primary-400">
                      ${product.selling_price.toFixed(2)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Cart */}
        <div className="card p-6 flex-1">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Cart ({items.length})
            </h2>
            {items.length > 0 && (
              <button
                onClick={clearCart}
                className="text-sm text-red-600 hover:text-red-700"
              >
                Clear All
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
              <FiShoppingCart className="h-12 w-12 mb-3" />
              <p>Cart is empty</p>
            </div>
          ) : (
            <div className="space-y-3 overflow-y-auto custom-scrollbar max-h-96">
              {items.map((item) => (
                <div
                  key={item.product_id}
                  className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg"
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 dark:text-gray-100">
                        {item.name}
                      </p>
                      <p className="text-sm text-gray-500">
                        ${item.unit_price.toFixed(2)} each
                      </p>
                    </div>
                    <button
                      onClick={() => removeItem(item.product_id)}
                      className="text-red-600 hover:text-red-700"
                    >
                      <FiTrash2 className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() =>
                          handleQuantityChange(
                            item.product_id,
                            item.quantity - 1
                          )
                        }
                        className="px-2 py-1 border rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                      >
                        -
                      </button>
                      <span className="w-12 text-center font-medium">
                        {item.quantity}
                      </span>
                      <button
                        onClick={() =>
                          handleQuantityChange(
                            item.product_id,
                            item.quantity + 1
                          )
                        }
                        className="px-2 py-1 border rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                      >
                        +
                      </button>
                    </div>
                    <p className="font-semibold text-primary-600 dark:text-primary-400">
                      ${item.total_price.toFixed(2)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right Panel - Checkout */}
      <div className="lg:w-96 card p-6 flex flex-col">
        <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
          Checkout
        </h2>

        <div className="space-y-4 flex-1">
          {/* Customer Info */}
          <div>
            <label className="label">Customer Name (Optional)</label>
            <input
              type="text"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              className="input"
              placeholder="Customer name"
            />
          </div>

          <div>
            <label className="label">Phone (Optional)</label>
            <input
              type="tel"
              value={customerPhone}
              onChange={(e) => setCustomerPhone(e.target.value)}
              className="input"
              placeholder="Phone number"
            />
          </div>

          {/* Payment Method */}
          <div>
            <label className="label">Payment Method</label>
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              className="input"
            >
              <option value="cash">Cash</option>
              <option value="card">Card</option>
              <option value="upi">UPI</option>
            </select>
          </div>

          {/* Amount Paid */}
          <div>
            <label className="label">Amount Paid</label>
            <input
              type="number"
              step="0.01"
              value={amountPaid}
              onChange={(e) => setAmountPaid(e.target.value)}
              className="input"
              placeholder="0.00"
            />
          </div>

          {/* Summary */}
          <div className="border-t pt-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">
                Subtotal:
              </span>
              <span className="font-medium">${subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-lg font-bold">
              <span>Total:</span>
              <span className="text-primary-600 dark:text-primary-400">
                ${subtotal.toFixed(2)}
              </span>
            </div>
            {amountPaid && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">
                  Change:
                </span>
                <span
                  className={`font-medium ${
                    change < 0 ? 'text-red-600' : 'text-green-600'
                  }`}
                >
                  ${change.toFixed(2)}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Complete Sale Button */}
        <button
          onClick={handleCompleteSale}
          disabled={items.length === 0 || isProcessing}
          className="btn-primary w-full mt-4 disabled:opacity-50"
        >
          {isProcessing ? 'Processing...' : 'Complete Sale'}
        </button>
      </div>
    </div>
  )
}
