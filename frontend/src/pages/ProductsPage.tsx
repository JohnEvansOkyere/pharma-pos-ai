import { useState, useEffect } from 'react'
import { api } from '../services/api'
import toast from 'react-hot-toast'
import { FiPlus, FiEdit, FiTrash } from 'react-icons/fi'

export default function ProductsPage() {
  const [products, setProducts] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    loadProducts()
  }, [])

  const loadProducts = async () => {
    setIsLoading(true)
    try {
      const data = await api.getProducts({ limit: 1000 })
      setProducts(data)
    } catch (error) {
      toast.error('Failed to load products')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Products
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Manage your inventory
          </p>
        </div>
        <button className="btn-primary flex items-center">
          <FiPlus className="mr-2" />
          Add Product
        </button>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Category
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  SKU
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Stock
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Expiry Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Cost Price
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Selling Price
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {products.map((product) => {
                // Calculate expiry status
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

                // Format product name (remove strength if present)
                const productName = product.name.split(/\d+mg|\d+ml/i)[0].trim()
                const strength = product.strength || product.name.match(/\d+mg|\d+ml/i)?.[0] || ''

                return (
                  <tr key={product.id}>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {product.id}
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-medium text-gray-900 dark:text-gray-100">
                        {productName} {strength}
                      </div>
                      {product.generic_name && (
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {product.generic_name}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className="capitalize text-sm text-gray-600 dark:text-gray-400">
                        {product.category_name || product.dosage_form}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {product.sku}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`px-2 py-1 text-xs rounded-full ${
                          product.total_stock <= product.low_stock_threshold
                            ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400'
                            : 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                        }`}
                      >
                        {product.total_stock}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {product.nearest_expiry ? (
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${expiryBg} ${expiryColor}`}>
                          {new Date(product.nearest_expiry).toLocaleDateString('en-GB')}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 font-medium text-gray-900 dark:text-gray-100">
                      GH₵ {product.cost_price.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 font-medium text-gray-900 dark:text-gray-100">
                      GH₵ {product.selling_price.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 space-x-2">
                      <button className="text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300">
                        <FiEdit />
                      </button>
                      <button className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300">
                        <FiTrash />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
