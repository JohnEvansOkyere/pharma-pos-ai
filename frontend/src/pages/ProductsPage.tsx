import { useState, useEffect } from 'react'
import { api } from '../services/api'
import toast from 'react-hot-toast'
import { FiPlus, FiEdit, FiTrash, FiX, FiSearch, FiPackage, FiDollarSign, FiLayers } from 'react-icons/fi'

export default function ProductsPage() {
  const [products, setProducts] = useState<any[]>([])
  const [categories, setCategories] = useState<any[]>([])
  const [suppliers, setSuppliers] = useState<any[]>([])
  const [showModal, setShowModal] = useState(false)
  const [editingProduct, setEditingProduct] = useState<any | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [catalogQuery, setCatalogQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalProducts, setTotalProducts] = useState(0)
  const [isLoadingProducts, setIsLoadingProducts] = useState(false)
  const [showReceiptModal, setShowReceiptModal] = useState(false)
  const [receivingProduct, setReceivingProduct] = useState<any | null>(null)
  const [isReceivingStock, setIsReceivingStock] = useState(false)
  const [showPricingModal, setShowPricingModal] = useState(false)
  const [pricingProduct, setPricingProduct] = useState<any | null>(null)
  const [isSavingPricing, setIsSavingPricing] = useState(false)
  const [showBatchesModal, setShowBatchesModal] = useState(false)
  const [batchProduct, setBatchProduct] = useState<any | null>(null)
  const [isLoadingProductDetail, setIsLoadingProductDetail] = useState(false)
  const [editingBatch, setEditingBatch] = useState<any | null>(null)
  const [isSavingBatch, setIsSavingBatch] = useState(false)
  const [receiveOpeningStock, setReceiveOpeningStock] = useState(true)
  const [formData, setFormData] = useState({
    name: '',
    generic_name: '',
    sku: '',
    barcode: '',
    dosage_form: 'TABLET',
    strength: '',
    manufacturer: '',
    supplier_id: '',
    cost_price: '',
    selling_price: '',
    wholesale_price: '',
    mrp: '',
    low_stock_threshold: '10',
    reorder_level: '20',
    reorder_quantity: '100',
    category_id: '',
    is_active: true,
    batch_number: '',
    initial_quantity: '',
    expiry_date: '',
    manufacture_date: '',
    location: '',
  })
  const [receiptForm, setReceiptForm] = useState({
    batch_number: '',
    quantity: '',
    expiry_date: '',
    cost_price: '',
    selling_price: '',
    wholesale_price: '',
    mrp: '',
    location: '',
    reason: 'Stock receipt',
  })
  const [priceForm, setPriceForm] = useState({
    cost_price: '',
    selling_price: '',
    wholesale_price: '',
    mrp: '',
  })
  const [batchForm, setBatchForm] = useState({
    batch_number: '',
    expiry_date: '',
    location: '',
    is_quarantined: false,
    quarantine_reason: '',
  })

  useEffect(() => {
    loadCategories()
    loadSuppliers()
  }, [])

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setCatalogQuery(searchQuery.trim())
      setCurrentPage(1)
    }, 250)

    return () => window.clearTimeout(timeoutId)
  }, [searchQuery])

  useEffect(() => {
    loadProducts(currentPage, catalogQuery)
  }, [currentPage, catalogQuery])

  const loadProducts = async (page = currentPage, query = catalogQuery) => {
    setIsLoadingProducts(true)
    try {
      const limit = 25
      const skip = (page - 1) * limit
      const data = await api.getProductsCatalog({
        limit,
        skip,
        q: query || undefined,
        is_active: true,
      })
      setProducts(data.items)
      setTotalProducts(data.total)
    } catch (error) {
      toast.error('Failed to load products')
    } finally {
      setIsLoadingProducts(false)
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

  const loadProductDetail = async (productId: number) => {
    setIsLoadingProductDetail(true)
    try {
      return await api.getProduct(productId)
    } finally {
      setIsLoadingProductDetail(false)
    }
  }

  const populateEditForm = (product: any) => {
    setFormData({
      name: product.name || '',
      generic_name: product.generic_name || '',
      sku: product.sku || '',
      barcode: product.barcode || '',
      dosage_form: product.dosage_form || 'TABLET',
      strength: product.strength || '',
      manufacturer: product.manufacturer || '',
      supplier_id: product.supplier_id?.toString() || '',
      cost_price: product.cost_price?.toString() || '',
      selling_price: product.selling_price?.toString() || '',
      wholesale_price: product.wholesale_price?.toString() || '',
      mrp: product.mrp?.toString() || '',
      low_stock_threshold: product.low_stock_threshold?.toString() || '10',
      reorder_level: product.reorder_level?.toString() || '20',
      reorder_quantity: product.reorder_quantity?.toString() || '100',
      category_id: product.category_id?.toString() || '',
      is_active: product.is_active ?? true,
      batch_number: '',
      initial_quantity: '',
      expiry_date: '',
      manufacture_date: '',
      location: '',
    })
    setReceiveOpeningStock(false)
  }

  // ========== NEW: AUTO-GENERATION FUNCTIONS ==========
  const buildProductCode = (value: string) => {
    const cleaned = value.replace(/[^a-zA-Z0-9 ]/g, ' ').trim().toUpperCase()
    if (!cleaned) return ''

    const primaryWord = cleaned.split(/\s+/).find((word) => /[A-Z]/.test(word)) || ''
    if (!primaryWord) return ''

    const lettersOnly = primaryWord.replace(/[^A-Z]/g, '')
    if (!lettersOnly) return ''

    const firstLetter = lettersOnly[0]
    const consonants = lettersOnly
      .slice(1)
      .split('')
      .filter((char) => !'AEIOU'.includes(char))
    const fallbackLetters = lettersOnly.slice(1).split('')

    const codeChars = [firstLetter]
    for (const char of consonants) {
      if (codeChars.length >= 3) break
      if (!codeChars.includes(char)) {
        codeChars.push(char)
      }
    }
    for (const char of fallbackLetters) {
      if (codeChars.length >= 3) break
      if (!codeChars.includes(char)) {
        codeChars.push(char)
      }
    }

    return codeChars.join('').slice(0, 3)
  }

  const generateSKU = () => {
    const nameSource = formData.name.trim() || formData.generic_name.trim()
    const productCode = buildProductCode(nameSource)
    const strengthSource = formData.strength.trim() || formData.name
    const strengthMatch = strengthSource.match(/(\d+(?:\.\d+)?)/)
    const strengthCode = strengthMatch ? strengthMatch[1].replace('.', '') : ''
    const formCode = formData.dosage_form.trim().slice(0, 3).toUpperCase()

    if (productCode && strengthCode) {
      return `${productCode}-${strengthCode}`
    }

    if (productCode && formCode && formCode !== 'TAB') {
      return `${productCode}-${formCode}`
    }

    if (productCode) {
      return productCode
    }

    const categoryPrefix = formData.category_id
      ? categories
          .find((c) => c.id.toString() === formData.category_id)
          ?.name.replace(/[^a-zA-Z]/g, '')
          .slice(0, 3)
          .toUpperCase() || 'PRD'
      : 'PRD'
    const timestamp = Date.now().toString().slice(-4)
    return `${categoryPrefix}-${timestamp}`
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

    const masterData: any = {
      name: formData.name.trim(),
      generic_name: formData.generic_name.trim() || null,
      sku: formData.sku.trim(),
      barcode: formData.barcode.trim() || null,
      dosage_form: formData.dosage_form,
      strength: formData.strength.trim() || null,
      manufacturer: formData.manufacturer.trim() || null,
      low_stock_threshold: parseInt(formData.low_stock_threshold),
      reorder_level: parseInt(formData.reorder_level),
      reorder_quantity: parseInt(formData.reorder_quantity),
      category_id: parseInt(formData.category_id),
      supplier_id: formData.supplier_id ? parseInt(formData.supplier_id) : null,
      is_active: formData.is_active
    }

    try {
      if (editingProduct) {
        await api.updateProduct(editingProduct.id, masterData)
        toast.success('Product master data updated')
      } else {
        const productData: any = {
          ...masterData,
          cost_price: parseFloat(formData.cost_price),
          selling_price: parseFloat(formData.selling_price),
          wholesale_price: formData.wholesale_price ? parseFloat(formData.wholesale_price) : null,
          mrp: formData.mrp ? parseFloat(formData.mrp) : null,
        }
        const createdProduct = await api.createProduct(productData)

        if (receiveOpeningStock) {
          await api.receiveProductStock(createdProduct.id, {
            batch_number: formData.batch_number.trim(),
            quantity: parseInt(formData.initial_quantity, 10),
            expiry_date: formData.expiry_date,
            manufacture_date: formData.manufacture_date || undefined,
            location: formData.location.trim() || undefined,
            cost_price: parseFloat(formData.cost_price),
            selling_price: parseFloat(formData.selling_price),
            wholesale_price: formData.wholesale_price ? parseFloat(formData.wholesale_price) : undefined,
            mrp: formData.mrp ? parseFloat(formData.mrp) : undefined,
            reason: 'Opening stock',
          })
        }

        toast.success('Product created successfully')
      }
      setShowModal(false)
      resetForm()
      await loadProducts(1, catalogQuery)
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

  const handleEdit = async (product: any) => {
    try {
      const detail = await loadProductDetail(product.id)
      setEditingProduct(detail)
      populateEditForm(detail)
      setShowModal(true)
    } catch (error) {
      toast.error('Failed to open edit form')
    }
  }

  const handleDelete = async (productId: number) => {
    if (!confirm('Are you sure you want to delete this product?')) return

    try {
      await api.deleteProduct(productId)
      toast.success('Product deleted successfully')
      await loadProducts(currentPage, catalogQuery)
    } catch (error) {
      toast.error('Failed to delete product')
    }
  }

  const handleOpenReceiptModal = (product: any) => {
    setReceivingProduct(product)
    setReceiptForm({
      batch_number: '',
      quantity: '',
      expiry_date: '',
      cost_price: product.cost_price?.toString() || '',
      selling_price: product.selling_price?.toString() || '',
      wholesale_price: product.wholesale_price?.toString() || '',
      mrp: product.mrp?.toString() || '',
      location: '',
      reason: 'Stock receipt',
    })
    setShowReceiptModal(true)
  }

  const handleOpenPricingModal = async (product: any) => {
    try {
      const detail = await loadProductDetail(product.id)
      setPricingProduct(detail)
      setPriceForm({
        cost_price: detail.cost_price?.toString() || '',
        selling_price: detail.selling_price?.toString() || '',
        wholesale_price: detail.wholesale_price?.toString() || '',
        mrp: detail.mrp?.toString() || '',
      })
      setShowPricingModal(true)
    } catch (error) {
      toast.error('Failed to load product pricing')
    }
  }

  const handleOpenBatchesModal = async (product: any) => {
    try {
      const detail = await loadProductDetail(product.id)
      setEditingBatch(null)
      setBatchProduct(detail)
      setShowBatchesModal(true)
    } catch (error) {
      toast.error('Failed to load product batches')
    }
  }

  const handleOpenBatchEditor = (batch: any) => {
    setEditingBatch(batch)
    setBatchForm({
      batch_number: batch.batch_number || '',
      expiry_date: batch.expiry_date || '',
      location: batch.location || '',
      is_quarantined: !!batch.is_quarantined,
      quarantine_reason: batch.quarantine_reason || '',
    })
  }

  const handleReceiveStock = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!receivingProduct) return

    setIsReceivingStock(true)
    try {
      await api.receiveProductStock(receivingProduct.id, {
        batch_number: receiptForm.batch_number.trim(),
        quantity: parseInt(receiptForm.quantity, 10),
        expiry_date: receiptForm.expiry_date,
        cost_price: parseFloat(receiptForm.cost_price),
        selling_price: receiptForm.selling_price ? parseFloat(receiptForm.selling_price) : undefined,
        wholesale_price: receiptForm.wholesale_price ? parseFloat(receiptForm.wholesale_price) : undefined,
        mrp: receiptForm.mrp ? parseFloat(receiptForm.mrp) : undefined,
        location: receiptForm.location.trim() || undefined,
        reason: receiptForm.reason.trim() || 'Stock receipt',
      })

      toast.success('Stock received successfully')
      setShowReceiptModal(false)
      setReceivingProduct(null)
      await loadProducts(currentPage, catalogQuery)
    } catch (error: any) {
      const errorDetail = error.response?.data?.detail
      toast.error(typeof errorDetail === 'string' ? errorDetail : 'Failed to receive stock')
    } finally {
      setIsReceivingStock(false)
    }
  }

  const handleSavePricing = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!pricingProduct) return

    setIsSavingPricing(true)
    try {
      await api.updateProduct(pricingProduct.id, {
        cost_price: parseFloat(priceForm.cost_price),
        selling_price: parseFloat(priceForm.selling_price),
        wholesale_price: priceForm.wholesale_price ? parseFloat(priceForm.wholesale_price) : null,
        mrp: priceForm.mrp ? parseFloat(priceForm.mrp) : null,
      })
      toast.success('Product pricing updated')
      setShowPricingModal(false)
      setPricingProduct(null)
      await loadProducts(currentPage, catalogQuery)
    } catch (error: any) {
      const errorDetail = error.response?.data?.detail
      toast.error(typeof errorDetail === 'string' ? errorDetail : 'Failed to update pricing')
    } finally {
      setIsSavingPricing(false)
    }
  }

  const handleSaveBatch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!batchProduct || !editingBatch) return

    setIsSavingBatch(true)
    try {
      await api.updateProductBatch(batchProduct.id, editingBatch.id, {
        batch_number: batchForm.batch_number.trim(),
        expiry_date: batchForm.expiry_date,
        location: batchForm.location.trim() || null,
        is_quarantined: batchForm.is_quarantined,
        quarantine_reason: batchForm.is_quarantined
          ? batchForm.quarantine_reason.trim()
          : null,
      })

      const refreshedProduct = await loadProductDetail(batchProduct.id)
      setBatchProduct(refreshedProduct)
      setEditingBatch(null)
      toast.success('Batch updated successfully')
      await loadProducts(currentPage, catalogQuery)
    } catch (error: any) {
      const errorDetail = error.response?.data?.detail
      toast.error(typeof errorDetail === 'string' ? errorDetail : 'Failed to update batch')
    } finally {
      setIsSavingBatch(false)
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
      manufacturer: '',
      supplier_id: '',
      cost_price: '',
      selling_price: '',
      wholesale_price: '',
      mrp: '',
      low_stock_threshold: '10',
      reorder_level: '20',
      reorder_quantity: '100',
      category_id: '',
      is_active: true,
      batch_number: '',
      initial_quantity: '',
      expiry_date: '',
      manufacture_date: '',
      location: '',
    })
    setEditingProduct(null)
    setReceiveOpeningStock(true)
  }

  const totalPages = Math.max(1, Math.ceil(totalProducts / 25))

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Products
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Manage product master data, prices, and received stock.
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
        <div className="border-b border-gray-200 dark:border-gray-700 p-4">
          <label className="relative block">
            <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10"
              placeholder="Search by product name, generic name, SKU, barcode, or category"
            />
          </label>
        </div>
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
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => handleOpenReceiptModal(product)}
                          className="inline-flex items-center rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-300 dark:hover:bg-emerald-900/30"
                          title="Receive stock"
                        >
                          <FiPackage className="mr-1" />
                          Receive
                        </button>
                        <button
                          onClick={() => handleOpenPricingModal(product)}
                          className="inline-flex items-center rounded-md bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100 dark:bg-amber-900/20 dark:text-amber-300 dark:hover:bg-amber-900/30"
                          title="Update pricing"
                        >
                          <FiDollarSign className="mr-1" />
                          Prices
                        </button>
                        <button
                          onClick={() => handleOpenBatchesModal(product)}
                          className="inline-flex items-center rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
                          title="View product batches"
                        >
                          <FiLayers className="mr-1" />
                          Batches
                        </button>
                        <button
                          onClick={() => handleEdit(product)}
                          className="inline-flex items-center rounded-md bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-700 hover:bg-primary-100 dark:bg-primary-900/20 dark:text-primary-300 dark:hover:bg-primary-900/30"
                          title="Edit product master data"
                        >
                          <FiEdit className="mr-1" />
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(product.id)}
                          className="inline-flex items-center rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-300 dark:hover:bg-red-900/30"
                          title="Deactivate product"
                        >
                          <FiTrash className="mr-1" />
                          Deactivate
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
              {!isLoadingProducts && products.length === 0 && (
                <tr>
                  <td
                    colSpan={9}
                    className="px-6 py-8 text-center text-sm text-gray-500 dark:text-gray-400"
                  >
                    No products match your search.
                  </td>
                </tr>
              )}
              {isLoadingProducts && (
                <tr>
                  <td
                    colSpan={9}
                    className="px-6 py-8 text-center text-sm text-gray-500 dark:text-gray-400"
                  >
                    Loading products...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3 text-sm text-gray-600 dark:border-gray-700 dark:text-gray-400">
          <div>
            {totalProducts === 0
              ? 'No products found'
              : `Showing ${(currentPage - 1) * 25 + 1}-${Math.min(currentPage * 25, totalProducts)} of ${totalProducts}`}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
              className="btn-secondary"
              disabled={currentPage === 1 || isLoadingProducts}
            >
              Previous
            </button>
            <span>
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
              className="btn-secondary"
              disabled={currentPage >= totalPages || isLoadingProducts}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Add/Edit Product Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {editingProduct ? 'Edit Product Master Data' : 'Add New Product'}
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
                {!editingProduct && (
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/40">
                    <label className="inline-flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={receiveOpeningStock}
                        onChange={(e) => setReceiveOpeningStock(e.target.checked)}
                        className="mt-1 h-4 w-4"
                      />
                      <span>
                        <span className="block text-sm font-medium text-gray-900 dark:text-gray-100">
                          Receive opening stock now
                        </span>
                        <span className="block text-sm text-gray-600 dark:text-gray-400">
                          Leave this on to create the product and receive the first batch together. Turn it off to save the product first and receive stock later.
                        </span>
                      </span>
                    </label>
                  </div>
                )}

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
                        Manufacturer
                      </label>
                      <input
                        type="text"
                        value={formData.manufacturer}
                        onChange={(e) => setFormData({ ...formData, manufacturer: e.target.value })}
                        className="input"
                        placeholder="Manufacturer or brand owner"
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
                          placeholder="e.g., AMX-500"
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

                {/* Product Details */}
                <div>
                  <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                    Product Details
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
                  </div>
                </div>

                {!editingProduct && (
                  <div>
                    <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                      Pricing (GH₵)
                    </h3>
                    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
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
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          MRP
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          value={formData.mrp}
                          onChange={(e) => setFormData({ ...formData, mrp: e.target.value })}
                          className="input"
                        />
                      </div>
                    </div>
                  </div>
                )}

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
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
                        {suppliers.map((supplier) => (
                          <option key={supplier.id} value={supplier.id}>
                            {supplier.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <label className="inline-flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-3">
                      <input
                        type="checkbox"
                        checked={formData.is_active}
                        onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                        className="h-4 w-4"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300">
                        Product is active and available for sale
                      </span>
                    </label>
                  </div>
                </div>

                {/* Opening Stock (for new products) */}
                {!editingProduct && receiveOpeningStock && (
                  <div>
                    <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                      Opening Stock
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
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
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Manufacture Date
                        </label>
                        <input
                          type="date"
                          value={formData.manufacture_date}
                          onChange={(e) => setFormData({ ...formData, manufacture_date: e.target.value })}
                          className="input"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Location
                        </label>
                        <input
                          type="text"
                          value={formData.location}
                          onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                          className="input"
                          placeholder="Shelf or storage bin"
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
                    {editingProduct ? 'Save Master Data' : 'Create Product'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {showReceiptModal && receivingProduct && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    Receive Stock
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    {receivingProduct.name} ({receivingProduct.sku})
                  </p>
                </div>
                <button
                  onClick={() => {
                    setShowReceiptModal(false)
                    setReceivingProduct(null)
                  }}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                >
                  <FiX className="h-6 w-6" />
                </button>
              </div>

              <form onSubmit={handleReceiveStock} className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Batch Number *
                    </label>
                    <input
                      type="text"
                      required
                      value={receiptForm.batch_number}
                      onChange={(e) => setReceiptForm({ ...receiptForm, batch_number: e.target.value })}
                      className="input"
                      placeholder="Supplier batch number"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Quantity Received *
                    </label>
                    <input
                      type="number"
                      min="1"
                      required
                      value={receiptForm.quantity}
                      onChange={(e) => setReceiptForm({ ...receiptForm, quantity: e.target.value })}
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
                      value={receiptForm.expiry_date}
                      onChange={(e) => setReceiptForm({ ...receiptForm, expiry_date: e.target.value })}
                      className="input"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Location
                    </label>
                    <input
                      type="text"
                      value={receiptForm.location}
                      onChange={(e) => setReceiptForm({ ...receiptForm, location: e.target.value })}
                      className="input"
                      placeholder="Shelf or bin location"
                    />
                  </div>
                </div>

                <div>
                  <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
                    Pricing Update
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Cost Price *
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        required
                        value={receiptForm.cost_price}
                        onChange={(e) => setReceiptForm({ ...receiptForm, cost_price: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Selling Price
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={receiptForm.selling_price}
                        onChange={(e) => setReceiptForm({ ...receiptForm, selling_price: e.target.value })}
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
                        min="0.01"
                        value={receiptForm.wholesale_price}
                        onChange={(e) => setReceiptForm({ ...receiptForm, wholesale_price: e.target.value })}
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        MRP
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={receiptForm.mrp}
                        onChange={(e) => setReceiptForm({ ...receiptForm, mrp: e.target.value })}
                        className="input"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Reason
                  </label>
                  <textarea
                    value={receiptForm.reason}
                    onChange={(e) => setReceiptForm({ ...receiptForm, reason: e.target.value })}
                    className="input min-h-24"
                    placeholder="Optional note for this stock receipt"
                  />
                </div>

                <div className="flex justify-end space-x-3 pt-4 border-t dark:border-gray-700">
                  <button
                    type="button"
                    onClick={() => {
                      setShowReceiptModal(false)
                      setReceivingProduct(null)
                    }}
                    className="btn-secondary"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn-primary" disabled={isReceivingStock}>
                    {isReceivingStock ? 'Receiving...' : 'Receive Stock'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {showPricingModal && pricingProduct && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-xl w-full">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    Update Pricing
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    {pricingProduct.name} ({pricingProduct.sku})
                  </p>
                </div>
                <button
                  onClick={() => {
                    setShowPricingModal(false)
                    setPricingProduct(null)
                  }}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                >
                  <FiX className="h-6 w-6" />
                </button>
              </div>

              <form onSubmit={handleSavePricing} className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Cost Price *
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      required
                      value={priceForm.cost_price}
                      onChange={(e) => setPriceForm({ ...priceForm, cost_price: e.target.value })}
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
                      min="0.01"
                      required
                      value={priceForm.selling_price}
                      onChange={(e) => setPriceForm({ ...priceForm, selling_price: e.target.value })}
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
                      min="0.01"
                      value={priceForm.wholesale_price}
                      onChange={(e) => setPriceForm({ ...priceForm, wholesale_price: e.target.value })}
                      className="input"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      MRP
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={priceForm.mrp}
                      onChange={(e) => setPriceForm({ ...priceForm, mrp: e.target.value })}
                      className="input"
                    />
                  </div>
                </div>

                <div className="flex justify-end space-x-3 pt-4 border-t dark:border-gray-700">
                  <button
                    type="button"
                    onClick={() => {
                      setShowPricingModal(false)
                      setPricingProduct(null)
                    }}
                    className="btn-secondary"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn-primary" disabled={isSavingPricing}>
                    {isSavingPricing ? 'Saving...' : 'Save Prices'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {showBatchesModal && batchProduct && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    Product Batches
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    {batchProduct.name} ({batchProduct.sku}) · Stock {batchProduct.total_stock}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setEditingBatch(null)
                    setShowBatchesModal(false)
                    setBatchProduct(null)
                  }}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                >
                  <FiX className="h-6 w-6" />
                </button>
              </div>

              {batchProduct.batches?.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 dark:bg-gray-800">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Batch</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Quantity</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Expiry</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Received</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Location</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {[...batchProduct.batches]
                        .sort((a: any, b: any) => new Date(a.expiry_date).getTime() - new Date(b.expiry_date).getTime())
                        .map((batch: any) => (
                          <tr key={batch.id}>
                            <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{batch.batch_number}</td>
                            <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{batch.quantity}</td>
                            <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                              {new Date(batch.expiry_date).toLocaleDateString('en-GB')}
                            </td>
                            <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                              {batch.received_date ? new Date(batch.received_date).toLocaleDateString('en-GB') : '-'}
                            </td>
                            <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{batch.location || '-'}</td>
                            <td className="px-4 py-3">
                              <span
                                className={`rounded-full px-2 py-1 text-xs font-medium ${
                                  batch.is_quarantined
                                    ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-300'
                                    : 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-300'
                                }`}
                              >
                                {batch.is_quarantined ? 'Quarantined' : 'Available'}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <button
                                onClick={() => handleOpenBatchEditor(batch)}
                                className="inline-flex items-center rounded-md bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-700 hover:bg-primary-100 dark:bg-primary-900/20 dark:text-primary-300 dark:hover:bg-primary-900/30"
                              >
                                <FiEdit className="mr-1" />
                                Manage
                              </button>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  This product has no recorded batches yet.
                </p>
              )}

              <div className="mt-6 rounded-lg bg-slate-50 p-4 text-sm text-slate-600 dark:bg-slate-900/20 dark:text-slate-300">
                Use the Receive action to add new stock batches. Use Stock Adjustments for quantity corrections, damages, expiries, and returns so every stock change remains traceable.
              </div>

              {editingBatch && (
                <div className="mt-6 rounded-lg border border-gray-200 p-5 dark:border-gray-700">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                      Manage Batch
                    </h3>
                    <button
                      onClick={() => setEditingBatch(null)}
                      className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                    >
                      Close
                    </button>
                  </div>

                  <form onSubmit={handleSaveBatch} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Batch Number *
                        </label>
                        <input
                          type="text"
                          required
                          value={batchForm.batch_number}
                          onChange={(e) => setBatchForm({ ...batchForm, batch_number: e.target.value })}
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
                          value={batchForm.expiry_date}
                          onChange={(e) => setBatchForm({ ...batchForm, expiry_date: e.target.value })}
                          className="input"
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Location
                        </label>
                        <input
                          type="text"
                          value={batchForm.location}
                          onChange={(e) => setBatchForm({ ...batchForm, location: e.target.value })}
                          className="input"
                          placeholder="Shelf or storage bin"
                        />
                      </div>
                    </div>

                    <label className="inline-flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-3">
                      <input
                        type="checkbox"
                        checked={batchForm.is_quarantined}
                        onChange={(e) =>
                          setBatchForm({
                            ...batchForm,
                            is_quarantined: e.target.checked,
                            quarantine_reason: e.target.checked ? batchForm.quarantine_reason : '',
                          })
                        }
                        className="h-4 w-4"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300">
                        Quarantine this batch and exclude it from sellable stock
                      </span>
                    </label>

                    {batchForm.is_quarantined && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Quarantine Reason *
                        </label>
                        <textarea
                          required
                          value={batchForm.quarantine_reason}
                          onChange={(e) => setBatchForm({ ...batchForm, quarantine_reason: e.target.value })}
                          className="input min-h-24"
                          placeholder="Explain why this batch is quarantined"
                        />
                      </div>
                    )}

                    <div className="flex justify-end gap-3 pt-2">
                      <button
                        type="button"
                        onClick={() => setEditingBatch(null)}
                        className="btn-secondary"
                      >
                        Cancel
                      </button>
                      <button type="submit" className="btn-primary" disabled={isSavingBatch}>
                        {isSavingBatch ? 'Saving...' : 'Save Batch'}
                      </button>
                    </div>
                  </form>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
