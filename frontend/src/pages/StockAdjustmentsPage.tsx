import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { FiRefreshCw, FiSearch } from 'react-icons/fi'

import { api } from '../services/api'

interface Product {
  id: number
  name: string
  sku: string
  total_stock: number
}

interface ProductBatch {
  id: number
  batch_number: string
  quantity: number
  expiry_date: string
  is_quarantined: boolean
}

interface ProductDetail extends Product {
  batches: ProductBatch[]
}

interface StockAdjustment {
  id: number
  product_id: number
  batch_id?: number | null
  adjustment_type: string
  quantity: number
  reason: string
  performed_by?: number | null
  created_at: string
}

const adjustmentTypes = [
  { value: 'damage', label: 'Damaged Stock' },
  { value: 'expired', label: 'Expired Write-Off' },
  { value: 'subtraction', label: 'Stock Removal' },
  { value: 'addition', label: 'Stock Addition' },
  { value: 'return', label: 'Return To Stock' },
  { value: 'correction', label: 'Batch Correction' },
]

const batchRequiredTypes = new Set(['addition', 'return', 'correction', 'expired'])

export default function StockAdjustmentsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [selectedProductId, setSelectedProductId] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<ProductDetail | null>(null)
  const [adjustments, setAdjustments] = useState<StockAdjustment[]>([])
  const [productSearch, setProductSearch] = useState('')
  const [isLoadingProducts, setIsLoadingProducts] = useState(true)
  const [isLoadingAdjustments, setIsLoadingAdjustments] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formData, setFormData] = useState({
    adjustment_type: 'damage',
    batch_id: '',
    quantity: '',
    reason: '',
  })

  useEffect(() => {
    loadProducts()
    loadAdjustments()
  }, [])

  useEffect(() => {
    if (!selectedProductId) {
      setSelectedProduct(null)
      setFormData((current) => ({ ...current, batch_id: '' }))
      return
    }

    loadProductDetails(Number(selectedProductId))
  }, [selectedProductId])

  const availableBatches = useMemo(() => {
    if (!selectedProduct) return []
    return selectedProduct.batches.filter((batch) => batch.quantity > 0)
  }, [selectedProduct])

  const filteredProducts = useMemo(() => {
    const query = productSearch.trim().toLowerCase()
    if (!query) return products

    return products.filter((product) => {
      const haystack = `${product.name} ${product.sku}`.toLowerCase()
      return haystack.includes(query)
    })
  }, [products, productSearch])

  const isBatchRequired = batchRequiredTypes.has(formData.adjustment_type)

  const loadProducts = async () => {
    setIsLoadingProducts(true)
    try {
      const data = await api.getProducts({ limit: 1000, is_active: true })
      setProducts(data)
    } catch (error) {
      toast.error('Failed to load products')
    } finally {
      setIsLoadingProducts(false)
    }
  }

  const loadProductDetails = async (productId: number) => {
    try {
      const data = await api.getProduct(productId)
      setSelectedProduct(data)
    } catch (error) {
      toast.error('Failed to load product batches')
    }
  }

  const loadAdjustments = async () => {
    setIsLoadingAdjustments(true)
    try {
      const data = await api.getStockAdjustments({ limit: 100 })
      setAdjustments(data)
    } catch (error) {
      toast.error('Failed to load stock adjustments')
    } finally {
      setIsLoadingAdjustments(false)
    }
  }

  const resetForm = () => {
    setFormData({
      adjustment_type: 'damage',
      batch_id: '',
      quantity: '',
      reason: '',
    })
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()

    if (!selectedProductId) {
      toast.error('Select a product first')
      return
    }

    if (isBatchRequired && !formData.batch_id) {
      toast.error('Select a batch for this adjustment type')
      return
    }

    setIsSubmitting(true)
    try {
      const payload = {
        product_id: Number(selectedProductId),
        adjustment_type: formData.adjustment_type,
        quantity: Number(formData.quantity),
        reason: formData.reason.trim(),
        batch_id: formData.batch_id ? Number(formData.batch_id) : undefined,
      }

      await api.createStockAdjustment(payload)
      toast.success('Stock adjustment recorded')
      resetForm()
      await Promise.all([
        loadAdjustments(),
        loadProducts(),
        loadProductDetails(Number(selectedProductId)),
      ])
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to record stock adjustment')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Stock Adjustments
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Record damaged, expired, returned, added, or corrected stock.
          </p>
        </div>
        <button
          onClick={() => {
            loadProducts()
            loadAdjustments()
            if (selectedProductId) {
              loadProductDetails(Number(selectedProductId))
            }
          }}
          className="btn-secondary flex items-center"
        >
          <FiRefreshCw className="mr-2" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="card p-6 xl:col-span-1">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            New Adjustment
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Product</label>
              <label className="relative mb-2 block">
                <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={productSearch}
                  onChange={(e) => setProductSearch(e.target.value)}
                  className="input pl-10"
                  placeholder="Search product by name or SKU"
                />
              </label>
              <select
                value={selectedProductId}
                onChange={(e) => setSelectedProductId(e.target.value)}
                className="input"
                required
                disabled={isLoadingProducts}
              >
                <option value="">Select product</option>
                {filteredProducts.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} ({product.sku}) - Stock {product.total_stock}
                  </option>
                ))}
              </select>
              {!isLoadingProducts && filteredProducts.length === 0 && (
                <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                  No products match your search.
                </p>
              )}
            </div>

            <div>
              <label className="label">Adjustment Type</label>
              <select
                value={formData.adjustment_type}
                onChange={(e) =>
                  setFormData((current) => ({
                    ...current,
                    adjustment_type: e.target.value,
                    batch_id: '',
                  }))
                }
                className="input"
                required
              >
                {adjustmentTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="label">
                Batch {isBatchRequired ? '(Required)' : '(Optional)'}
              </label>
              <select
                value={formData.batch_id}
                onChange={(e) => setFormData((current) => ({ ...current, batch_id: e.target.value }))}
                className="input"
                disabled={!selectedProduct}
                required={isBatchRequired}
              >
                <option value="">Select batch</option>
                {availableBatches.map((batch) => (
                  <option key={batch.id} value={batch.id}>
                    {batch.batch_number} - Qty {batch.quantity} - Exp {new Date(batch.expiry_date).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="label">Quantity</label>
              <input
                type="number"
                min="1"
                value={formData.quantity}
                onChange={(e) => setFormData((current) => ({ ...current, quantity: e.target.value }))}
                className="input"
                required
              />
            </div>

            <div>
              <label className="label">Reason</label>
              <textarea
                value={formData.reason}
                onChange={(e) => setFormData((current) => ({ ...current, reason: e.target.value }))}
                className="input min-h-28"
                placeholder="Explain why this stock change is being recorded"
                required
              />
            </div>

            <button
              type="submit"
              className="btn-primary w-full"
              disabled={isSubmitting || isLoadingProducts}
            >
              {isSubmitting ? 'Saving...' : 'Save Adjustment'}
            </button>
          </form>
        </div>

        <div className="space-y-6 xl:col-span-2">
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
              Product Batches
            </h2>

            {!selectedProduct ? (
              <p className="text-gray-500 dark:text-gray-400">
                Select a product to see its batches.
              </p>
            ) : availableBatches.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400">
                No available batches for this product.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Batch
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Quantity
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Expiry
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {availableBatches.map((batch) => {
                      const expiryDate = new Date(batch.expiry_date)
                      const daysUntilExpiry = Math.ceil((expiryDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
                      let status = 'Healthy'
                      let statusClass = 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'

                      if (daysUntilExpiry <= 30) {
                        status = 'Near Expiry'
                        statusClass = 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                      } else if (daysUntilExpiry <= 90) {
                        status = 'Watch'
                        statusClass = 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300'
                      }

                      return (
                        <tr key={batch.id}>
                          <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                            {batch.batch_number}
                          </td>
                          <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                            {batch.quantity}
                          </td>
                          <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                            {new Date(batch.expiry_date).toLocaleDateString()}
                          </td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusClass}`}>
                              {batch.is_quarantined ? 'Quarantined' : status}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
              Recent Adjustments
            </h2>

            {isLoadingAdjustments ? (
              <p className="text-gray-500 dark:text-gray-400">Loading adjustments...</p>
            ) : adjustments.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400">No stock adjustments recorded yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Product ID
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Batch
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Type
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Quantity
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Reason
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Date
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {adjustments.map((adjustment) => (
                      <tr key={adjustment.id}>
                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                          {adjustment.product_id}
                        </td>
                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                          {adjustment.batch_id || 'Mixed / N/A'}
                        </td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 uppercase">
                            {adjustment.adjustment_type.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                          {adjustment.quantity}
                        </td>
                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                          {adjustment.reason}
                        </td>
                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                          {new Date(adjustment.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
