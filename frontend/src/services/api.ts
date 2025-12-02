/**
 * API client for backend communication.
 * Handles authentication, request/response interceptors, and error handling.
 */
import axios, { AxiosInstance, AxiosError } from 'axios'
import toast from 'react-hot-toast'

// Use nginx proxy (/api) in production, or direct API URL in development
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
    // Request interceptor - Add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('auth_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // Response interceptor - Handle errors
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Unauthorized - clear token and redirect to login
          localStorage.removeItem('auth_token')
          localStorage.removeItem('user')
          window.location.href = '/login'
          toast.error('Session expired. Please login again.')
        } else if (error.response?.status === 403) {
          toast.error('You do not have permission to perform this action.')
        } else if (error.response && error.response.status >= 500) {
          toast.error('Server error. Please try again later.')
        }

        return Promise.reject(error)
      }
    )
  }

  // Auth endpoints
  async login(username: string, password: string) {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)

    const response = await this.client.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })
    return response.data
  }

  async register(userData: any) {
    const response = await this.client.post('/auth/register', userData)
    return response.data
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me')
    return response.data
  }

  // Product endpoints
  async getProducts(params?: any) {
    const response = await this.client.get('/products', { params })
    return response.data
  }

  async searchProducts(query: string) {
    const response = await this.client.get('/products/search', {
      params: { q: query },
    })
    return response.data
  }

  async getProduct(id: number) {
    const response = await this.client.get(`/products/${id}`)
    return response.data
  }

  async createProduct(productData: any) {
    const response = await this.client.post('/products', productData)
    return response.data
  }

  async updateProduct(id: number, productData: any) {
    const response = await this.client.put(`/products/${id}`, productData)
    return response.data
  }

  async deleteProduct(id: number) {
    await this.client.delete(`/products/${id}`)
  }

  async getLowStockProducts() {
    const response = await this.client.get('/products/low-stock')
    return response.data
  }

  async createProductBatch(productId: number, batchData: any) {
    const response = await this.client.post(`/products/${productId}/batches`, batchData)
    return response.data
  }

  // Category endpoints
  async getCategories() {
    const response = await this.client.get('/categories')
    return response.data
  }

  async createCategory(categoryData: any) {
    const response = await this.client.post('/categories', categoryData)
    return response.data
  }

  // Supplier endpoints
  async getSuppliers(params?: any) {
    const response = await this.client.get('/suppliers', { params })
    return response.data
  }

  async createSupplier(supplierData: any) {
    const response = await this.client.post('/suppliers', supplierData)
    return response.data
  }

  // Sales endpoints
  async createSale(saleData: any) {
    const response = await this.client.post('/sales', saleData)
    return response.data
  }

  async getSales(params?: any) {
    const response = await this.client.get('/sales', { params })
    return response.data
  }

  async getSale(id: number) {
    const response = await this.client.get(`/sales/${id}`)
    return response.data
  }

  async getTodaySalesSummary() {
    const response = await this.client.get('/sales/summary/today')
    return response.data
  }

  // Dashboard endpoints
  async getDashboardKPIs() {
    const response = await this.client.get('/dashboard/kpis')
    return response.data
  }

  async getFastMovingProducts(params?: any) {
    const response = await this.client.get('/dashboard/fast-moving-products', {
      params,
    })
    return response.data
  }

  async getSlowMovingProducts(params?: any) {
    const response = await this.client.get('/dashboard/slow-moving-products', {
      params,
    })
    return response.data
  }

  async getSalesTrend(params?: any) {
    const response = await this.client.get('/dashboard/sales-trend', { params })
    return response.data
  }

  async getStaffPerformance(params?: any) {
    const response = await this.client.get('/dashboard/staff-performance', {
      params,
    })
    return response.data
  }

  async getExpiringProducts(params?: any) {
    const response = await this.client.get('/dashboard/expiring-products', {
      params,
    })
    return response.data
  }

  async getLowStockItems(params?: any) {
  const response = await this.client.get('/dashboard/low-stock-items', {
    params,
  })
  return response.data
}

  async getOverstockItems() {
    const response = await this.client.get('/dashboard/overstock-items')
    return response.data
  }

  async getProfitByCategory(params?: any) {
    const response = await this.client.get('/dashboard/profit-by-category', {
      params,
    })
    return response.data
  }

  async getRevenueAnalysis(params?: any) {
    const response = await this.client.get('/dashboard/revenue-analysis', {
      params,
    })
    return response.data
  }

  async getFinancialKPIs(params?: any) {
    const response = await this.client.get('/dashboard/financial-kpis', {
      params,
    })
    return response.data
  }

  // Notification endpoints
  async getNotifications(params?: any) {
    const response = await this.client.get('/notifications', { params })
    return response.data
  }

  async getUnreadCount() {
    const response = await this.client.get('/notifications/unread-count')
    return response.data
  }

  async markNotificationAsRead(id: number) {
    const response = await this.client.put(`/notifications/${id}`, {
      is_read: true,
    })
    return response.data
  }

  async markAllNotificationsAsRead() {
    const response = await this.client.put('/notifications/mark-all-read')
    return response.data
  }

  // AI Insights endpoints
  async getDeadStock(days?: number) {
    const response = await this.client.get('/insights/dead-stock', {
      params: { days },
    })
    return response.data
  }

  async getReorderSuggestion(productId: number, analysisDays?: number) {
    const response = await this.client.get(
      `/insights/reorder-suggestion/${productId}`,
      { params: { analysis_days: analysisDays } }
    )
    return response.data
  }

  async getProfitMarginAnalysis() {
    const response = await this.client.get('/insights/profit-margin-analysis')
    return response.data
  }

  // Users endpoints (Admin only)
  async getUsers() {
    const response = await this.client.get('/users')
    return response.data
  }

  async createUser(userData: any) {
    const response = await this.client.post('/users', userData)
    return response.data
  }

  async updateUser(userId: number, userData: any) {
    const response = await this.client.put(`/users/${userId}`, userData)
    return response.data
  }

  async deleteUser(userId: number) {
    await this.client.delete(`/users/${userId}`)
  }
}

export const api = new ApiClient()
