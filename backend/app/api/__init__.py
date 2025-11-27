"""
API package initialization.
"""
from fastapi import APIRouter

from app.api.endpoints import (
    auth,
    users,
    products,
    categories,
    suppliers,
    sales,
    notifications,
    dashboard,
    insights,
)

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(products.router)
api_router.include_router(categories.router)
api_router.include_router(suppliers.router)
api_router.include_router(sales.router)
api_router.include_router(notifications.router)
api_router.include_router(dashboard.router)
api_router.include_router(insights.router)
