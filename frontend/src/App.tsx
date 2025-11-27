import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useEffect } from 'react'
import { useAuthStore } from './stores/authStore'

// Pages
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ProductsPage from './pages/ProductsPage'
import POSPage from './pages/POSPage'
import SalesPage from './pages/SalesPage'
import SuppliersPage from './pages/SuppliersPage'
import NotificationsPage from './pages/NotificationsPage'
import SettingsPage from './pages/SettingsPage'

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
          <Route path="products" element={<ProductsPage />} />
          <Route path="pos" element={<POSPage />} />
          <Route path="sales" element={<SalesPage />} />
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
    </BrowserRouter>
  )
}

export default App
