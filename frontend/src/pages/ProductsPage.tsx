import { useState, useEffect } from 'react'
import { api } from '../services/api'
import toast from 'react-hot-toast'
import { FiPlus, FiEdit, FiTrash, FiX } from 'react-icons/fi'

export default function ProductsPage() {
  const [products, setProducts] = useState<any[]>([])
  const [categories, setCategories] = useState<any[]>([])
  const [suppliers, setSuppliers] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingProduct, setEditingProduct] = useState<any | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    generic_name: '',
    sku: '',
    barcode: '',
    description: '',
    dosage_form: 'tablet',
    strength: '',
    prescription_status: 'otc',
    active_ingredient: '',
    manufacturer: '',
    cost_price: '',
    selling_price: '',
    wholesale_price: '',
    low_stock_threshold: '10',
    reorder_level: '20',
    reorder_quantity: '100',
    category_id: '',
    supplier_id: '',
    is_active: true
  })

  useEffect(() => {
    loadProducts()
    loadCategories()
    loadSuppliers()
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

  const loadCategories = async () => {
    try {
      const data = await api.getCategories()
      setCategories(data)
    } catch (error) {
      console.error('Failed to load categories')
    }
  }

  const loadSuppliers = async () => {
    try {
      const data = await api.getSuppliers()
      setSuppliers(data)
    } catch (error) {
      console.error('Failed to load suppliers')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const productData = {
      ...formData,
      cost_price: parseFloat(formData.cost_price),
      selling_price: parseFloat(formData.selling_price),
      wholesale_price: formData.wholesale_price ? parseFloat(formData.wholesale_price) : undefined,
      low_stock_threshold: parseInt(formData.low_stock_threshold),
      reorder_level: parseInt(formData.reorder_level),
      reorder_quantity: parseInt(formData.reorder_quantity),
      category_id: parseInt(formData.category_id),
      supplier_id: formData.supplier_id ? parseInt(formData.supplier_id) : undefined
    }

    try {
      if (editingProduct) {
        await api.updateProduct(editingProduct.id, productData)
        toast.success('Product updated successfully')
      } else {
        await api.createProduct(productData)
        toast.success('Product created successfully')
      }
      setShowModal(false)
      resetForm()
      loadProducts()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to save product')
    }
  }

  const handleEdit = (product: any) => {
    setEditingProduct(product)
    setFormData({
      name: product.name,
      generic_name: product.generic_name || '',
      sku: product.sku,
      barcode: product.barcode || '',
      description: product.description || '',
      dosage_form: product.dosage_form,
      strength: product.strength || '',
      prescription_status: product.prescription_status,
      active_ingredient: product.active_ingredient || '',
      manufacturer: product.manufacturer || '',
      cost_price: product.cost_price.toString(),
      selling_price: product.selling_price.toString(),
      wholesale_price: product.wholesale_price?.toString() || '',
      low_stock_threshold: product.low_stock_threshold.toString(),
      reorder_level: product.reorder_level.toString(),
      reorder_quantity: product.reorder_quantity.toString(),
      category_id: product.category_id.toString(),
      supplier_id: product.supplier_id?.toString() || '',
      is_active: product.is_active
    })
    setShowModal(true)
  }

  const handleDelete = async (productId: number) => {
    if (!confirm('Are you sure you want to delete this product?')) return

    try {
      await api.deleteProduct(productId)
      toast.success('Product deleted successfully')
      loadProducts()
    } catch (error) {
      toast.error('Failed to delete product')
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      generic_name: '',
      sku: '',
      barcode: '',
      description: '',
      dosage_form: 'tablet',
      strength: '',
      prescription_status: 'otc',
      active_ingredient: '',
      manufacturer: '',
      cost_price: '',
      selling_price: '',
      wholesale_price: '',
      low_stock_threshold: '10',
      reorder_level: '20',
      reorder_quantity: '100',
      category_id: '',
      supplier_id: '',
      is_active: true
    })
    setEditingProduct(null)
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
        <button
          onClick={() => {
            resetForm()
            setShowModal(true)
          }}
          className="btn-primary flex items-center"
        >
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
                      <button
                        onClick={() => handleEdit(product)}
                        className="text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                      >
                        <FiEdit />
                      </button>
                      <button
                        onClick={() => handleDelete(product.id)}
                        className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                      >
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

      {/* Add/Edit Product Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {editingProduct ? 'Edit Product' : 'Add New Product'}
                </h2>
                <button
                  onClick={() => {
                    setShowModal(false)
                    resetForm()
                  }}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                >
                  <FiX className="h-6 w-6" />
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Basic Information */}
                <div>
                  <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                    Basic Information
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Product Name *
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Generic Name
                      </label>
                      <input
                        type="text"
                        value={formData.generic_name}
                        onChange={(e) => setFormData({ ...formData, generic_name: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        SKU *
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.sku}
                        onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Barcode
                      </label>
                      <input
                        type="text"
                        value={formData.barcode}
                        onChange={(e) => setFormData({ ...formData, barcode: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Description
                      </label>
                      <textarea
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        className="input"
                        rows={3}
                      />
                    </div>
                  </div>
                </div>

                {/* Pharmaceutical Information */}
                <div>
                  <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                    Pharmaceutical Information
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Dosage Form *
                      </label>
                      <select
                        required
                        value={formData.dosage_form}
                        onChange={(e) => setFormData({ ...formData, dosage_form: e.target.value })}
                        className="input"
                      >
                        <option value="tablet">Tablet</option>
                        <option value="capsule">Capsule</option>
                        <option value="syrup">Syrup</option>
                        <option value="injection">Injection</option>
                        <option value="cream">Cream</option>
                        <option value="ointment">Ointment</option>
                        <option value="drops">Drops</option>
                        <option value="inhaler">Inhaler</option>
                        <option value="powder">Powder</option>
                        <option value="suppository">Suppository</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Strength
                      </label>
                      <input
                        type="text"
                        placeholder="e.g., 500mg"
                        value={formData.strength}
                        onChange={(e) => setFormData({ ...formData, strength: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Prescription Status *
                      </label>
                      <select
                        required
                        value={formData.prescription_status}
                        onChange={(e) => setFormData({ ...formData, prescription_status: e.target.value })}
                        className="input"
                      >
                        <option value="otc">OTC</option>
                        <option value="prescription">Prescription</option>
                        <option value="controlled">Controlled</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Active Ingredient
                      </label>
                      <input
                        type="text"
                        value={formData.active_ingredient}
                        onChange={(e) => setFormData({ ...formData, active_ingredient: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Manufacturer
                      </label>
                      <input
                        type="text"
                        value={formData.manufacturer}
                        onChange={(e) => setFormData({ ...formData, manufacturer: e.target.value })}
                        className="input"
                      />
                    </div>
                  </div>
                </div>

                {/* Pricing */}
                <div>
                  <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                    Pricing (GH₵)
                  </h3>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Cost Price *
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        value={formData.cost_price}
                        onChange={(e) => setFormData({ ...formData, cost_price: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Selling Price *
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        value={formData.selling_price}
                        onChange={(e) => setFormData({ ...formData, selling_price: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Wholesale Price
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.wholesale_price}
                        onChange={(e) => setFormData({ ...formData, wholesale_price: e.target.value })}
                        className="input"
                      />
                    </div>
                  </div>
                </div>

                {/* Inventory */}
                <div>
                  <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                    Inventory Settings
                  </h3>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Low Stock Threshold
                      </label>
                      <input
                        type="number"
                        value={formData.low_stock_threshold}
                        onChange={(e) => setFormData({ ...formData, low_stock_threshold: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Reorder Level
                      </label>
                      <input
                        type="number"
                        value={formData.reorder_level}
                        onChange={(e) => setFormData({ ...formData, reorder_level: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Reorder Quantity
                      </label>
                      <input
                        type="number"
                        value={formData.reorder_quantity}
                        onChange={(e) => setFormData({ ...formData, reorder_quantity: e.target.value })}
                        className="input"
                      />
                    </div>
                  </div>
                </div>

                {/* Category & Supplier */}
                <div>
                  <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                    Classification
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Category *
                      </label>
                      <select
                        required
                        value={formData.category_id}
                        onChange={(e) => setFormData({ ...formData, category_id: e.target.value })}
                        className="input"
                      >
                        <option value="">Select Category</option>
                        {categories.map((cat) => (
                          <option key={cat.id} value={cat.id}>
                            {cat.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Supplier
                      </label>
                      <select
                        value={formData.supplier_id}
                        onChange={(e) => setFormData({ ...formData, supplier_id: e.target.value })}
                        className="input"
                      >
                        <option value="">Select Supplier</option>
                        {suppliers.map((sup) => (
                          <option key={sup.id} value={sup.id}>
                            {sup.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Form Actions */}
                <div className="flex justify-end space-x-3 pt-4 border-t dark:border-gray-700">
                  <button
                    type="button"
                    onClick={() => {
                      setShowModal(false)
                      resetForm()
                    }}
                    className="btn-secondary"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn-primary">
                    {editingProduct ? 'Update Product' : 'Create Product'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
