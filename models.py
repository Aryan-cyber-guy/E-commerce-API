"""Pydantic models for request and response validation."""

from datetime import datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel, EmailStr, Field

from db_model import Category, OrderStatus, PaymentStatus, UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None


class UserResponse(BaseModel):
    id: int
    name: str | None = None
    email: str
    role: UserRole
    created_at: datetime
    updated_at: datetime
    is_active: bool


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=8, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal = Field(gt=0, decimal_places=2, max_digits=10)
    category: Category
    stock_quantity: int = Field(ge=0)
    image_url: str | None = Field(default=None, max_length=255)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=10)
    category: Category | None = None
    stock_quantity: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=255)


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    price: Decimal
    category: Category
    stock_quantity: int
    image_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductPagination(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    has_previous: bool
    has_next: bool
    products: List[ProductResponse]


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class CartItemUpdate(BaseModel):
    quantity: int | None = Field(default=None, gt=0)


class CartItemResponse(BaseModel):
    id:int
    product_id: int
    name: str
    price: Decimal
    stock_quantity: int
    image_url: str | None = None
    quantity: int


class OrderResponse(BaseModel):
    id: int
    user_id: int
    status: OrderStatus
    total_amount: Decimal
    payment_status: PaymentStatus
    created_at: datetime


class OrderPagination(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    has_previous: bool
    has_next: bool
    orders: List[OrderResponse]