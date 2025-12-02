import { useState, useEffect } from 'react'
import { api } from '../services/api'
import toast from 'react-hot-toast'
import { FiPlus, FiEdit, FiTrash, FiX } from 'react-icons/fi'

export default function ProductsPage() {
  const [products, setProducts] = useState<any[]>([])
  const [categories, setCategories] = useState<any[]>([])
  const [suppliers, setSuppliers] = useState<any[]>([])
  const [showModal, setShowModal] = useState(false)
  const [editingProduct, setEditingProduct] = useState<any | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    generic_name: '',
    sku: '',
    barcode: '',
    dosage_form: 'TABLET',
    strength: '',
    prescription_status: 'OTC',
    cost_price: '',
    selling_price: '',
    wholesale_price: '',
    low_stock_threshold: '10',
    reorder_level: '20',
    reorder_quantity: '100',
    category_id: '',
    is_active: true,
    // Initial batch information
    batch_number: '',
    initial_quantity: '',
    expiry_date: ''
  })

  useEffect(() => {
    loadProducts()
    loadCategories()
    loadSuppliers()
  }, [])

  const loadProducts = async () => {
    try {
      const data = await api.getProducts({ limit: 1000 })
      setProducts(data)
    } catch (error) {
      toast.error('Failed to load products')
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

  // ========== NEW: AUTO-GENERATION FUNCTIONS ==========
  const generateSKU = () => {
    const prefix = formData.category_id ? 
      categories.find(c => c.id.toString() === formData.category_id)?.name.substring(0, 3).toUpperCase() || 'PRD' 
      : 'PRD'
    const timestamp = Date.now().toString().slice(-6)
    const random = Math.random().toString(36).substring(2, 5).toUpperCase()
    return `${prefix}-${timestamp}${random}`
  }

  const generateBarcode = () => {
    // Generate 13-digit EAN barcode (Ghana country code: 620)
    const countryCode = '620'
    const random = Math.floor(Math.random() * 1000000000).toString().padStart(9, '0')
    return `${countryCode}${random}`
  }

  const generateBatchNumber = () => {
    const date = new Date()
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const random = Math.random().toString(36).substring(2, 6).toUpperCase()
    return `BATCH${year}${month}${day}${random}`
  }
  // ========== END AUTO-GENERATION FUNCTIONS ==========

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Build product data - only include fields that backend expects
    const productData: any = {
      name: formData.name,
      generic_name: formData.generic_name || null,
      sku: formData.sku,
      barcode: formData.barcode || null,
      dosage_form: formData.dosage_form,
      strength: formData.strength || null,
      prescription_status: formData.prescription_status,
      cost_price: parseFloat(formData.cost_price),
      selling_price: parseFloat(formData.selling_price),
      wholesale_price: formData.wholesale_price ? parseFloat(formData.wholesale_price) : null,
      low_stock_threshold: parseInt(formData.low_stock_threshold),
      reorder_level: parseInt(formData.reorder_level),
      reorder_quantity: parseInt(formData.reorder_quantity),
      category_id: parseInt(formData.category_id),
      is_active: formData.is_active
    }

    try {
      if (editingProduct) {
        await api.updateProduct(editingProduct.id, productData)
        toast.success('Product updated successfully')
      } else {
        // Create product first
        const createdProduct = await api.createProduct(productData)

        // If initial batch data is provided, create the batch
        if (formData.batch_number && formData.initial_quantity && formData.expiry_date) {
          const batchData = {
            product_id: createdProduct.id,
            batch_number: formData.batch_number,
            quantity: parseInt(formData.initial_quantity),
            expiry_date: formData.expiry_date,
            cost_price: parseFloat(formData.cost_price)
          }
          await api.createProductBatch(createdProduct.id, batchData)
        }

        toast.success('Product created successfully')
      }
      setShowModal(false)
      resetForm()
      loadProducts()
    } catch (error: any) {
      console.error('Save product error:', error)
      const errorDetail = error.response?.data?.detail
      if (typeof errorDetail === 'string') {
        toast.error(errorDetail)
      } else if (Array.isArray(errorDetail)) {
        toast.error(errorDetail.map((e: any) => e.msg).join(', '))
      } else {
        toast.error('Failed to save product')
      }
    }
  }

  const handleEdit = (product: any) => {
    console.log('Edit clicked for product:', product)
    
    try {
      setEditingProduct(product)
      setFormData({
        name: product.name || '',
        generic_name: product.generic_name || '',
        sku: product.sku || '',
        barcode: product.barcode || '',
        dosage_form: product.dosage_form || 'TABLET',
        strength: product.strength || '',
        prescription_status: product.prescription_status || 'OTC',
        cost_price: product.cost_price?.toString() || '',
        selling_price: product.selling_price?.toString() || '',
        wholesale_price: product.wholesale_price?.toString() || '',
        low_stock_threshold: product.low_stock_threshold?.toString() || '10',
        reorder_level: product.reorder_level?.toString() || '20',
        reorder_quantity: product.reorder_quantity?.toString() || '100',
        category_id: product.category_id?.toString() || '',
        is_active: product.is_active ?? true,
        batch_number: '',
        initial_quantity: '',
        expiry_date: ''
      })
      setShowModal(true)
      console.log('Modal should open now')
    } catch (error) {
      console.error('Edit error:', error)
      toast.error('Failed to open edit form')
    }
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
      dosage_form: 'TABLET',
      strength: '',
      prescription_status: 'OTC',
      cost_price: '',
      selling_price: '',
      wholesale_price: '',
      low_stock_threshold: '10',
      reorder_level: '20',
      reorder_quantity: '100',
      category_id: '',
      is_active: true,
      batch_number: '',
      initial_quantity: '',
      expiry_date: ''
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
        {/* ========== UPDATED: Auto-generate on modal open ========== */}
        <button
          onClick={() => {
            resetForm()
            // Auto-generate values when adding new product
            setFormData(prev => ({
              ...prev,
              sku: generateSKU(),
              barcode: generateBarcode(),
              batch_number: generateBatchNumber()
            }))
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
                    {/* ========== UPDATED: SKU with Auto Button ========== */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        SKU *
                      </label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          required
                          value={formData.sku}
                          onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                          className="input flex-1"
                          placeholder="Auto-generated"
                        />
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, sku: generateSKU() })}
                          className="px-3 py-2 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded hover:bg-primary-200 dark:hover:bg-primary-900/50 text-sm font-medium whitespace-nowrap"
                        >
                          Auto
                        </button>
                      </div>
                    </div>
                    {/* ========== UPDATED: Barcode with Auto Button ========== */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Barcode
                      </label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={formData.barcode}
                          onChange={(e) => setFormData({ ...formData, barcode: e.target.value })}
                          className="input flex-1"
                          placeholder="Auto-generated"
                        />
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, barcode: generateBarcode() })}
                          className="px-3 py-2 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded hover:bg-primary-200 dark:hover:bg-primary-900/50 text-sm font-medium whitespace-nowrap"
                        >
                          Auto
                        </button>
                      </div>
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
                        <option value="TABLET">Tablet</option>
                        <option value="CAPSULE">Capsule</option>
                        <option value="SYRUP">Syrup</option>
                        <option value="INJECTION">Injection</option>
                        <option value="SUSPENSION">Suspension</option>
                        <option value="CREAM">Cream</option>
                        <option value="OINTMENT">Ointment</option>
                        <option value="DROPS">Drops</option>
                        <option value="POWDER">Powder</option>
                        <option value="INHALER">Inhaler</option>
                        <option value="SUPPOSITORY">Suppository</option>
                        <option value="PATCH">Patch</option>
                        <option value="OTHER">Other</option>
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
                        <option value="OTC">OTC (Over The Counter)</option>
                        <option value="PRESCRIPTION_REQUIRED">Prescription Required</option>
                        <option value="PRESCRIPTION_OPTIONAL">Prescription Optional</option>
                      </select>
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

                {/* Category */}
                <div>
                  <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                    Classification
                  </h3>
                  <div className="grid grid-cols-1 gap-4">
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
                  </div>
                </div>

                {/* Initial Batch Information (for new products) */}
                {!editingProduct && (
                  <div>
                    <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                      Initial Stock Batch
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                      {/* ========== UPDATED: Batch Number with Auto Button ========== */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Batch Number *
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            required
                            value={formData.batch_number}
                            onChange={(e) => setFormData({ ...formData, batch_number: e.target.value })}
                            className="input flex-1"
                            placeholder="e.g., BATCH20250102ABCD"
                          />
                          <button
                            type="button"
                            onClick={() => setFormData({ ...formData, batch_number: generateBatchNumber() })}
                            className="px-3 py-2 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded hover:bg-primary-200 dark:hover:bg-primary-900/50 text-sm font-medium whitespace-nowrap"
                          >
                            Auto
                          </button>
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Initial Quantity *
                        </label>
                        <input
                          type="number"
                          required
                          min="0"
                          value={formData.initial_quantity}
                          onChange={(e) => setFormData({ ...formData, initial_quantity: e.target.value })}
                          className="input"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Expiry Date *
                        </label>
                        <input
                          type="date"
                          required
                          value={formData.expiry_date}
                          onChange={(e) => setFormData({ ...formData, expiry_date: e.target.value })}
                          className="input"
                        />
                      </div>
                    </div>
                  </div>
                )}

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