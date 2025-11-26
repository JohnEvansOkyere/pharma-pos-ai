import { useState, useEffect } from 'react'
import { api } from '../services/api'
import toast from 'react-hot-toast'
import { FiPlus } from 'react-icons/fi'

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    loadSuppliers()
  }, [])

  const loadSuppliers = async () => {
    setIsLoading(true)
    try {
      const data = await api.getSuppliers()
      setSuppliers(data)
    } catch (error) {
      toast.error('Failed to load suppliers')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Suppliers
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Manage your suppliers
          </p>
        </div>
        <button className="btn-primary flex items-center">
          <FiPlus className="mr-2" />
          Add Supplier
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {suppliers.map((supplier) => (
          <div key={supplier.id} className="card p-6">
            <h3 className="text-lg font-semibold mb-2">{supplier.name}</h3>
            <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <p>Contact: {supplier.contact_person || 'N/A'}</p>
              <p>Email: {supplier.email || 'N/A'}</p>
              <p>Phone: {supplier.phone || 'N/A'}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
