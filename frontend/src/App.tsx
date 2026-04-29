import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { lazy, Suspense, useEffect } from 'react'
import { useAuthStore } from './stores/authStore'

// Pages
const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const CloudDashboardPage = lazy(() => import('./pages/CloudDashboardPage'))
const ProductsPage = lazy(() => import('./pages/ProductsPage'))
const POSPage = lazy(() => import('./pages/POSPage'))
const SalesPage = lazy(() => import('./pages/SalesPage'))
const SuppliersPage = lazy(() => import('./pages/SuppliersPage'))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const StockAdjustmentsPage = lazy(() => import('./pages/StockAdjustmentsPage'))

// Layout
import MainLayout from './components/layout/MainLayout'

// Protected route component
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Admin-only route component
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (user?.role !== 'admin') {
    return <Navigate to="/pos" replace />
  }

  return <>{children}</>
}

// Admin or Manager route component
function AdminOrManagerRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (user?.role !== 'admin' && user?.role !== 'manager') {
    return <Navigate to="/pos" replace />
  }

  return <>{children}</>
}

function App() {
  const { loadUser } = useAuthStore()

  useEffect(() => {
    loadUser()
  }, [loadUser])

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#363636',
            color: '#fff',
          },
        }}
      />
      <Suspense fallback={<div className="p-6 text-sm text-gray-500">Loading...</div>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route
            path="/"
            element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/pos" replace />} />
            <Route path="dashboard" element={
              <AdminRoute>
                <DashboardPage />
              </AdminRoute>
            } />
            <Route path="cloud-dashboard" element={
              <AdminOrManagerRoute>
                <CloudDashboardPage />
              </AdminOrManagerRoute>
            } />
            <Route path="products" element={<ProductsPage />} />
            <Route path="pos" element={<POSPage />} />
            <Route path="sales" element={<SalesPage />} />
            <Route path="stock-adjustments" element={
              <AdminOrManagerRoute>
                <StockAdjustmentsPage />
              </AdminOrManagerRoute>
            } />
            <Route path="suppliers" element={<SuppliersPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="settings" element={
              <AdminOrManagerRoute>
                <SettingsPage />
              </AdminOrManagerRoute>
            } />
          </Route>

          <Route path="*" element={<Navigate to="/pos" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
