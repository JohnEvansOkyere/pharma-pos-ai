import { useState, useEffect } from 'react'
import { api } from '../services/api'
import toast from 'react-hot-toast'
import { FiChevronDown, FiChevronUp } from 'react-icons/fi'

interface SaleItem {
  id: number
  product_id: number
  quantity: number
  unit_price: number
  discount_amount: number
  total_price: number
  product_name?: string
}

interface Sale {
  id: number
  invoice_number: string
  customer_name?: string
  total_amount: number
  payment_method: string
  created_at: string
  items: SaleItem[]
}

export default function SalesPage() {
  const [sales, setSales] = useState<Sale[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [expandedSales, setExpandedSales] = useState<Set<number>>(new Set())
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  useEffect(() => {
    loadSales()
  }, [])

  const loadSales = async (filters?: { start_date?: string; end_date?: string }) => {
    setIsLoading(true)
    try {
      const params: any = { limit: 50 }
      if (filters?.start_date) params.start_date = filters.start_date
      if (filters?.end_date) params.end_date = filters.end_date

      const data = await api.getSales(params)
      setSales(data)
    } catch (error) {
      toast.error('Failed to load sales')
    } finally {
      setIsLoading(false)
    }
  }

  const handleFilter = () => {
    if (startDate && endDate && startDate > endDate) {
      toast.error('Start date must be before end date')
      return
    }
    loadSales({ start_date: startDate, end_date: endDate })
  }

  const handleClearFilter = () => {
    setStartDate('')
    setEndDate('')
    loadSales()
  }

  const toggleExpanded = (saleId: number) => {
    const newExpanded = new Set(expandedSales)
    if (newExpanded.has(saleId)) {
      newExpanded.delete(saleId)
    } else {
      newExpanded.add(saleId)
    }
    setExpandedSales(newExpanded)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Sales History
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          View all transactions
        </p>
      </div>

      {/* Date Filter */}
      <div className="card p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="input w-full"
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="input w-full"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleFilter}
              className="btn-primary px-6"
            >
              Filter
            </button>
            <button
              onClick={handleClearFilter}
              className="btn-secondary px-6"
            >
              Clear
            </button>
          </div>
        </div>
      </div>

      {/* Sales Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto custom-scrollbar">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">

                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Invoice
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Customer
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Total
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Payment
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Date
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {sales.map((sale) => (
                <>
                  <tr
                    key={sale.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
                    onClick={() => toggleExpanded(sale.id)}
                  >
                    <td className="px-6 py-4">
                      {expandedSales.has(sale.id) ? (
                        <FiChevronUp className="text-gray-600 dark:text-gray-400" />
                      ) : (
                        <FiChevronDown className="text-gray-600 dark:text-gray-400" />
                      )}
                    </td>
                    <td className="px-6 py-4 font-medium text-gray-900 dark:text-gray-100">
                      {sale.invoice_number}
                    </td>
                    <td className="px-6 py-4 text-gray-900 dark:text-gray-100">
                      {sale.customer_name || 'Walk-in'}
                    </td>
                    <td className="px-6 py-4 font-semibold text-primary-600">
                      GH₵ {sale.total_amount.toFixed(2)}
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                        {sale.payment_method}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                      {new Date(sale.created_at).toLocaleString()}
                    </td>
                  </tr>

                  {/* Expanded Row - Line Items */}
                  {expandedSales.has(sale.id) && (
                    <tr>
                      <td colSpan={6} className="px-6 py-4 bg-gray-50 dark:bg-gray-900">
                        <div className="ml-8">
                          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                            Invoice Items
                          </h4>
                          <div className="overflow-x-auto">
                            <table className="w-full">
                              <thead className="bg-gray-100 dark:bg-gray-800">
                                <tr>
                                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600 dark:text-gray-400">
                                    Product
                                  </th>
                                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-600 dark:text-gray-400">
                                    Quantity
                                  </th>
                                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-600 dark:text-gray-400">
                                    Unit Price
                                  </th>
                                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-600 dark:text-gray-400">
                                    Discount
                                  </th>
                                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-600 dark:text-gray-400">
                                    Total
                                  </th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                                {sale.items && sale.items.length > 0 ? (
                                  sale.items.map((item) => (
                                    <tr key={item.id}>
                                      <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                                        {item.product_name || `Product #${item.product_id}`}
                                      </td>
                                      <td className="px-4 py-2 text-sm text-right text-gray-900 dark:text-gray-100">
                                        {item.quantity}
                                      </td>
                                      <td className="px-4 py-2 text-sm text-right text-gray-900 dark:text-gray-100">
                                        GH₵ {item.unit_price.toFixed(2)}
                                      </td>
                                      <td className="px-4 py-2 text-sm text-right text-gray-600 dark:text-gray-400">
                                        GH₵ {item.discount_amount.toFixed(2)}
                                      </td>
                                      <td className="px-4 py-2 text-sm text-right font-semibold text-gray-900 dark:text-gray-100">
                                        GH₵ {item.total_price.toFixed(2)}
                                      </td>
                                    </tr>
                                  ))
                                ) : (
                                  <tr>
                                    <td colSpan={5} className="px-4 py-2 text-sm text-center text-gray-500">
                                      No items found
                                    </td>
                                  </tr>
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}

              {sales.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                    No sales found
                  </td>
                </tr>
              )}

              {isLoading && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                    Loading...
                  </td>
                </tr>
              )}
            </tbody>
            {sales.length > 0 && !isLoading && (
              <tfoot className="bg-gray-100 dark:bg-gray-800 border-t-2 border-gray-300 dark:border-gray-600">
                <tr>
                  <td colSpan={3} className="px-6 py-4 text-right font-bold text-gray-900 dark:text-gray-100">
                    Total Amount:
                  </td>
                  <td className="px-6 py-4 font-bold text-xl text-primary-600 dark:text-primary-400">
                    GH₵ {sales.reduce((sum, sale) => sum + sale.total_amount, 0).toFixed(2)}
                  </td>
                  <td colSpan={2}></td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>
    </div>
  )
}
