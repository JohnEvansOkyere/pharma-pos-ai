import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { useCartStore } from '../stores/cartStore'
import toast from 'react-hot-toast'
import { FiSearch, FiTrash2, FiShoppingCart, FiPrinter } from 'react-icons/fi'

interface Product {
  id: number
  name: string
  generic_name?: string
  sku: string
  barcode?: string
  dosage_form: string
  strength?: string
  selling_price: number
  total_stock: number
  manufacturer?: string
  nearest_expiry?: string
}

export default function POSPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [allProducts, setAllProducts] = useState<Product[]>([])
  const [filteredProducts, setFilteredProducts] = useState<Product[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [customerName, setCustomerName] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'momo'>('cash')
  const [momoNumber, setMomoNumber] = useState('')
  const [momoReference, setMomoReference] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [lastSale, setLastSale] = useState<any>(null)
  const [showPrintDialog, setShowPrintDialog] = useState(false)

  const { items, addItem, updateQuantity, removeItem, clearCart, getSubtotal } =
    useCartStore()

  // Load all products on mount
  useEffect(() => {
    loadAllProducts()
  }, [])

  // Filter products based on search query
  useEffect(() => {
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      const filtered = allProducts.filter(
        (p) =>
          p.name.toLowerCase().includes(query) ||
          p.generic_name?.toLowerCase().includes(query) ||
          p.sku.toLowerCase().includes(query) ||
          p.barcode?.toLowerCase().includes(query) ||
          p.manufacturer?.toLowerCase().includes(query)
      )
      setFilteredProducts(filtered)
    } else {
      setFilteredProducts(allProducts)
    }
  }, [searchQuery, allProducts])

  const loadAllProducts = async () => {
    setIsLoading(true)
    try {
      const products = await api.getProducts({ limit: 1000 })
      setAllProducts(products)
      setFilteredProducts(products)
    } catch (error) {
      console.error('Failed to load products:', error)
      toast.error('Failed to load products')
    } finally {
      setIsLoading(false)
    }
  }

  const handleAddToCart = (product: Product) => {
    try {
      addItem(
        {
          id: product.id,
          name: product.name,
          sku: product.sku,
          selling_price: product.selling_price,
          total_stock: product.total_stock,
        },
        1
      )
      toast.success(`Added ${product.name} to cart`)
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

    if (paymentMethod === 'momo' && !momoNumber) {
      toast.error('Please enter MOMO number')
      return
    }

    setIsProcessing(true)

    try {
      const total = getSubtotal()

      const saleData = {
        items: items.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity,
          unit_price: item.unit_price,
          discount_amount: item.discount_amount || 0,
        })),
        payment_method: paymentMethod,
        amount_paid: total,
        customer_name: customerName || undefined,
        customer_phone: customerPhone || undefined,
        momo_number: paymentMethod === 'momo' ? momoNumber : undefined,
        momo_reference: paymentMethod === 'momo' ? momoReference : undefined,
        discount_amount: 0,
        tax_amount: 0,
      }

      const sale = await api.createSale(saleData)

      setLastSale(sale)
      setShowPrintDialog(true)

      toast.success(`Sale completed! Invoice: ${sale.invoice_number}`)

      // Clear cart and form
      clearCart()
      setCustomerName('')
      setCustomerPhone('')
      setMomoNumber('')
      setMomoReference('')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Sale failed')
    } finally {
      setIsProcessing(false)
    }
  }

  const handlePrintReceipt = () => {
    // Show receipt before printing
    const receiptElement = document.querySelector('.receipt-print-area') as HTMLElement
    if (receiptElement) {
      receiptElement.style.display = 'block'
    }
    
    // Delay to ensure content is rendered
    setTimeout(() => {
      window.print()
      
      // Hide receipt after printing
      if (receiptElement) {
        receiptElement.style.display = 'none'
      }
      
      setShowPrintDialog(false)
      setLastSale(null)
    }, 100)
  }

  const subtotal = getSubtotal()

  return (
    <>
      <div className="h-screen flex flex-col lg:flex-row gap-6 p-6 overflow-hidden print:hidden">
        {/* Left Panel - All Products List */}
        <div className="flex-1 flex flex-col gap-6 min-h-0">
          {/* Search */}
          <div className="card p-6 flex-shrink-0">
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
                placeholder="Search by name, SKU, barcode, or manufacturer..."
                autoFocus
              />
            </div>
          </div>

          {/* All Products List */}
          <div className="card p-6 flex-1 flex flex-col min-h-0 overflow-hidden">
            <div className="flex justify-between items-center mb-4 flex-shrink-0">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {searchQuery ? 'Search Results' : 'All Products'} (
                {filteredProducts.length})
              </h2>
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="text-sm text-primary-600 hover:text-primary-700"
                >
                  Clear Search
                </button>
              )}
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              </div>
            ) : filteredProducts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                <p>No products found</p>
              </div>
            ) : (
              <div className="space-y-2 overflow-y-auto custom-scrollbar flex-1 min-h-0">
                {filteredProducts.map((product) => {
                  let expiryColor = 'text-green-600 dark:text-green-400'
                  let expiryBg = 'bg-green-50 dark:bg-green-900/20'

                  if (product.nearest_expiry) {
                    const expiryDate = new Date(product.nearest_expiry)
                    const today = new Date()
                    const daysUntilExpiry = Math.ceil((expiryDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))

                    if (daysUntilExpiry < 0) {
                      expiryColor = 'text-red-700 dark:text-red-400'
                      expiryBg = 'bg-red-50 dark:bg-red-900/20'
                    } else if (daysUntilExpiry <= 30) {
                      expiryColor = 'text-red-600 dark:text-red-400'
                      expiryBg = 'bg-red-50 dark:bg-red-900/20'
                    } else if (daysUntilExpiry <= 90) {
                      expiryColor = 'text-orange-600 dark:text-orange-400'
                      expiryBg = 'bg-orange-50 dark:bg-orange-900/20'
                    } else if (daysUntilExpiry <= 180) {
                      expiryColor = 'text-yellow-600 dark:text-yellow-400'
                      expiryBg = 'bg-yellow-50 dark:bg-yellow-900/20'
                    }
                  }

                  return (
                    <div
                      key={product.id}
                      onClick={() => handleAddToCart(product)}
                      className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer transition-colors"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {product.name}
                          </p>
                          <div className="mt-1 space-y-0.5">
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              {product.dosage_form}
                              {product.strength && ` • ${product.strength}`}
                            </p>
                            {product.manufacturer && (
                              <p className="text-xs text-gray-500 dark:text-gray-500">
                                {product.manufacturer}
                              </p>
                            )}
                            <p className="text-xs text-gray-500 dark:text-gray-500">
                              SKU: {product.sku} • Stock: {product.total_stock}
                            </p>
                            {product.nearest_expiry && (
                              <div className="mt-1">
                                <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${expiryBg} ${expiryColor}`}>
                                  Exp: {new Date(product.nearest_expiry).toLocaleDateString('en-GB')}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="text-right ml-4">
                          <p className="font-bold text-lg text-primary-600 dark:text-primary-400">
                            GH₵ {product.selling_price.toFixed(2)}
                          </p>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Middle Panel - Cart */}
        <div className="lg:w-80 card p-6 flex flex-col min-h-0 overflow-hidden">
          <div className="flex justify-between items-center mb-4 flex-shrink-0">
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
            <div className="flex flex-col items-center justify-center py-12 text-gray-400 flex-1">
              <FiShoppingCart className="h-12 w-12 mb-3" />
              <p>Cart is empty</p>
              <p className="text-xs mt-2">Click products to add</p>
            </div>
          ) : (
            <div className="space-y-3 overflow-y-auto custom-scrollbar flex-1">
              {items.map((item) => (
                <div
                  key={item.product_id}
                  className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg"
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1">
                      <p className="font-medium text-sm text-gray-900 dark:text-gray-100">
                        {item.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        GH₵ {item.unit_price.toFixed(2)} each
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
                          handleQuantityChange(item.product_id, item.quantity - 1)
                        }
                        className="px-2 py-1 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-sm font-medium"
                      >
                        -
                      </button>
                      <span className="w-12 text-center font-medium text-sm">
                        {item.quantity}
                      </span>
                      <button
                        onClick={() =>
                          handleQuantityChange(item.product_id, item.quantity + 1)
                        }
                        className="px-2 py-1 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-sm font-medium"
                      >
                        +
                      </button>
                    </div>
                    <p className="font-semibold text-primary-600 dark:text-primary-400">
                      GH₵ {item.total_price.toFixed(2)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Cart Total */}
          {items.length > 0 && (
            <div className="mt-4 pt-4 border-t flex-shrink-0">
              <div className="flex justify-between text-lg font-bold">
                <span>Total:</span>
                <span className="text-primary-600 dark:text-primary-400">
                  GH₵ {subtotal.toFixed(2)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Right Panel - Checkout */}
        <div className="lg:w-96 card p-6 flex flex-col min-h-0 overflow-hidden">
          <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100 flex-shrink-0">
            Checkout
          </h2>

          <div className="space-y-4 flex-1 overflow-y-auto custom-scrollbar min-h-0">
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
              <label className="label">Payment Method *</label>
              <select
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value as 'cash' | 'momo')}
                className="input"
              >
                <option value="cash">Cash</option>
                <option value="momo">Mobile Money (MOMO)</option>
              </select>
            </div>

            {/* MOMO Fields */}
            {paymentMethod === 'momo' && (
              <>
                <div>
                  <label className="label">MOMO Number *</label>
                  <input
                    type="tel"
                    value={momoNumber}
                    onChange={(e) => setMomoNumber(e.target.value)}
                    className="input"
                    placeholder="0XX XXX XXXX"
                    required
                  />
                </div>
                <div>
                  <label className="label">MOMO Reference (Optional)</label>
                  <input
                    type="text"
                    value={momoReference}
                    onChange={(e) => setMomoReference(e.target.value)}
                    className="input"
                    placeholder="Transaction reference"
                  />
                </div>
              </>
            )}

            {/* Summary */}
            <div className="border-t pt-4 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">
                  Items ({items.length}):
                </span>
                <span className="font-medium">GH₵ {subtotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-xl font-bold">
                <span>Total Amount:</span>
                <span className="text-primary-600 dark:text-primary-400">
                  GH₵ {subtotal.toFixed(2)}
                </span>
              </div>
              {paymentMethod === 'cash' && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  💡 Exact cash payment required
                </p>
              )}
            </div>
          </div>

          {/* Complete Sale Button */}
          <button
            onClick={handleCompleteSale}
            disabled={items.length === 0 || isProcessing}
            className="btn-primary w-full mt-4 disabled:opacity-50 flex-shrink-0"
          >
            {isProcessing ? 'Processing...' : `Complete Sale - GH₵ ${subtotal.toFixed(2)}`}
          </button>
        </div>

        {/* Print Dialog Modal */}
        {showPrintDialog && lastSale && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="card p-8 max-w-md w-full mx-4">
              <h2 className="text-2xl font-bold text-green-600 mb-4 text-center">
                ✅ Sale Completed!
              </h2>
              <div className="space-y-2 mb-6">
                <p className="text-center">
                  <span className="text-gray-600">Invoice:</span>{' '}
                  <span className="font-bold">{lastSale.invoice_number}</span>
                </p>
                <p className="text-center text-2xl font-bold text-primary-600">
                  GH₵ {lastSale.total_amount.toFixed(2)}
                </p>
                <p className="text-center text-sm text-gray-500">
                  Payment: {lastSale.payment_method === 'momo' ? 'Mobile Money' : 'Cash'}
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handlePrintReceipt}
                  className="btn-primary flex-1 flex items-center justify-center gap-2"
                >
                  <FiPrinter />
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

     {/* ========== RECEIPT PRINT TEMPLATE ========== */}
      {lastSale && (
        <div className="receipt-print-area" style={{ display: 'none' }}>
          <div style={{ 
            width: '80mm', 
            margin: '0 auto', 
            fontFamily: 'monospace', 
            fontSize: '12px',
            padding: '5mm',
            color: '#000',
            backgroundColor: '#fff'
          }}>
            {/* Header */}
            <div style={{ textAlign: 'center', marginBottom: '10px', paddingBottom: '10px', borderBottom: '2px dashed #000' }}>
              <h1 style={{ fontSize: '18px', fontWeight: 'bold', margin: '0 0 3px 0', color: '#000' }}>GYSBIN PHARMACY</h1>
              <p style={{ margin: '2px 0', fontSize: '10px' }}>P.O.BOX 12, Asuom</p>
              <p style={{ margin: '2px 0', fontSize: '10px' }}>Tel: 0XX XXX XXXX</p>
            </div>

            {/* Transaction Info */}
            <div style={{ marginBottom: '10px', fontSize: '10px', borderBottom: '1px dashed #000', paddingBottom: '8px' }}>
              <p style={{ margin: '2px 0' }}>Date: {new Date(lastSale.created_at).toLocaleString('en-GB')}</p>
              <p style={{ margin: '2px 0' }}>Invoice: <strong>{lastSale.invoice_number}</strong></p>
              <p style={{ margin: '2px 0' }}>Cashier: {lastSale.user_name || 'Admin'}</p>
              {lastSale.customer_name && (
                <p style={{ margin: '2px 0' }}>Customer: {lastSale.customer_name}</p>
              )}
              {lastSale.customer_phone && (
                <p style={{ margin: '2px 0' }}>Phone: {lastSale.customer_phone}</p>
              )}
            </div>

            {/* Items Table */}
            <div style={{ marginBottom: '10px' }}>
              <table style={{ width: '100%', fontSize: '10px', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px dashed #000' }}>
                    <th style={{ textAlign: 'left', paddingBottom: '5px', fontWeight: 'bold' }}>ITEM</th>
                    <th style={{ textAlign: 'center', paddingBottom: '5px', fontWeight: 'bold', width: '15%' }}>QTY</th>
                    <th style={{ textAlign: 'right', paddingBottom: '5px', fontWeight: 'bold', width: '20%' }}>PRICE</th>
                    <th style={{ textAlign: 'right', paddingBottom: '5px', fontWeight: 'bold', width: '20%' }}>TOTAL</th>
                  </tr>
                </thead>
                <tbody>
                  {lastSale.items.map((item: any, index: number) => (
                    <tr key={index}>
                      <td style={{ paddingTop: '5px', paddingBottom: '5px' }}>{item.product_name}</td>
                      <td style={{ textAlign: 'center', paddingTop: '5px', paddingBottom: '5px' }}>{item.quantity}</td>
                      <td style={{ textAlign: 'right', paddingTop: '5px', paddingBottom: '5px' }}>{item.unit_price.toFixed(2)}</td>
                      <td style={{ textAlign: 'right', paddingTop: '5px', paddingBottom: '5px' }}>{item.total_price.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Totals */}
            <div style={{ marginBottom: '10px', fontSize: '11px', borderTop: '1px dashed #000', paddingTop: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <span>Subtotal:</span>
                <span>GH₵ {lastSale.total_amount.toFixed(2)}</span>
              </div>
              {lastSale.discount_amount > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                  <span>Discount:</span>
                  <span>- GH₵ {lastSale.discount_amount.toFixed(2)}</span>
                </div>
              )}
              {lastSale.tax_amount > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                  <span>Tax:</span>
                  <span>GH₵ {lastSale.tax_amount.toFixed(2)}</span>
                </div>
              )}
              <div style={{ borderTop: '2px solid #000', paddingTop: '8px', marginTop: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '13px' }}>
                  <span>TOTAL:</span>
                  <span>GH₵ {lastSale.total_amount.toFixed(2)}</span>
                </div>
              </div>
              <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px dashed #000' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                  <span>Payment:</span>
                  <span>{lastSale.payment_method === 'momo' ? 'Mobile Money' : 'Cash'}</span>
                </div>
                {lastSale.payment_method === 'momo' && lastSale.momo_number && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', marginBottom: '3px' }}>
                    <span>MOMO:</span>
                    <span>{lastSale.momo_number}</span>
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                  <span>Amount Paid:</span>
                  <span>GH₵ {lastSale.amount_paid.toFixed(2)}</span>
                </div>
                {lastSale.change_amount > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '12px' }}>
                    <span>Change:</span>
                    <span>GH₵ {lastSale.change_amount.toFixed(2)}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Thank You Message */}
            <div style={{ textAlign: 'center', marginTop: '12px', paddingTop: '10px', borderTop: '2px dashed #000', fontSize: '11px' }}>
              <p style={{ fontWeight: 'bold', margin: '3px 0' }}>Thank you for your business!</p>
              <p style={{ margin: '3px 0' }}>Please come again!</p>
            </div>

            {/* Footer - More Compact */}
            <div style={{ textAlign: 'center', marginTop: '12px', paddingTop: '8px', borderTop: '1px dotted #000', fontSize: '8px' }}>
              <p style={{ margin: '1px 0' }}>Developed by: John Evans Okyere</p>
              <p style={{ margin: '1px 0' }}>Tel: +233 544 954 643</p>
            </div>
          </div>
        </div>
      )}
    </>
  )
}