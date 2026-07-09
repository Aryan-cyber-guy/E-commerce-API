"""SQLAlchemy models for the e-commerce domain."""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"


class Category(enum.Enum):
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    HOME = "home"
    BOOKS = "books"
    SPORTS = "sports"
    TOYS = "toys"
    BEAUTY = "beauty"


class OrderStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class Base(DeclarativeBase):
    pass


class DbUsers(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.USER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    cart: Mapped["Carts"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    orders: Mapped[list["Orders"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Products(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    price: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    category: Mapped[Category] = mapped_column(Enum(Category), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    cart_items: Mapped[list["CartItems"]] = relationship(back_populates="product")
    order_items: Mapped[list["OrderItems"]] = relationship(back_populates="product")


class Carts(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    user: Mapped["DbUsers"] = relationship(back_populates="cart")
    cart_items: Mapped[list["CartItems"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItems(Base):
    __tablename__ = "cartitems"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    cart: Mapped["Carts"] = relationship(back_populates="cart_items")
    product: Mapped["Products"] = relationship(back_populates="cart_items")


class Orders(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    total_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2))
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user: Mapped["DbUsers"] = relationship(back_populates="orders")
    order_items: Mapped[list["OrderItems"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payment: Mapped["Payments"] = relationship(back_populates="order", uselist=False, cascade="all, delete-orphan")


class OrderItems(Base):
    __tablename__ = "orderitems"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_at_purchase: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    order: Mapped["Orders"] = relationship(back_populates="order_items")
    product: Mapped["Products"] = relationship(back_populates="order_items")


class Payments(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True, unique=True, nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    order: Mapped["Orders"] = relationship(back_populates="payment")