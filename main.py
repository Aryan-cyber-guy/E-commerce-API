"""Main FastAPI application for the e-commerce API."""

import hashlib
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from redis import RedisError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api import cart, orders, products
from api.auth import (
    admin_required,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    verify_password,
    verify_token,
)
from api.cart import get_current_cart
from database import SessionLocal, get_db
from db_model import (
    Carts,
    DbUsers,
    OrderItems,
    Orders,
    OrderStatus,
    PaymentStatus,
    Payments,
    UserRole,
    Products
)
from models import PasswordUpdate, UserCreate, UserResponse, UserUpdate
from redis_client import redis_client

load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

def seed_admin() -> None:
    """Create a default admin user when env vars are present."""
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        return

    db = SessionLocal()
    try:
        admin = db.query(DbUsers).filter(DbUsers.email == ADMIN_EMAIL).first()
        if not admin:
            admin = DbUsers(email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD), role=UserRole.ADMIN)
            db.add(admin)
            db.commit()
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_admin()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "https://vanilla-joy-shop.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cart.router, prefix="/cart")
app.include_router(products.router, prefix="/products")
app.include_router(orders.router, prefix="/orders")

@app.get("/")
def check_up():
    """Health check endpoint."""
    return {"message": "Server is running"}


@app.get("/health")
def check_up():
    """Health check endpoint."""
    return {"message": "Server is running"}


@app.post("/auth/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user and create an initial cart."""
    email = user.email.strip().lower()
    existing_user = db.query(DbUsers).filter(DbUsers.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already registered")

    password_hashed = hash_password(user.password)
    new_user = DbUsers(email=email, password_hash=password_hashed)

    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except SQLAlchemyError:
        db.rollback()
        raise

    new_user.cart = Carts()
    try:
        db.commit()
        db.refresh(new_user)
    except SQLAlchemyError:
        db.rollback()
        raise

    return new_user


@app.patch("/users/me", response_model=UserResponse)
def update_user(data: UserUpdate, current_user: DbUsers = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update the current user's profile."""
    if data.name:
        current_user.name = data.name

    if data.email:
        email = data.email.strip().lower()
        existing_user = db.query(DbUsers).filter(DbUsers.email == email, DbUsers.id != current_user.id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email is already in use")
        current_user.email = email

    try:
        db.commit()
        db.refresh(current_user)
    except SQLAlchemyError:
        db.rollback()
        raise

    return current_user


@app.patch("/users/me/password")
def update_user_password(data: PasswordUpdate, current_user: DbUsers = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change the authenticated user's password."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if verify_password(data.new_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="New password must be different")

    current_user.password_hash = hash_password(data.new_password)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {"message": "Password updated successfully"}


@app.get("/users/me", response_model=UserResponse)
def read_current_user(current_user: DbUsers = Depends(get_current_user)):
    return current_user


@app.post("/auth/login", response_model=UserResponse)
async def login(request: Request, response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate a user and set auth cookies."""
    email = form_data.username.strip().lower()
    ip = request.client.host if request.client else "unknown"
    key = f"login_attempts:{ip}:{email}"

    try:
        attempts = redis_client.incr(key)
        if attempts == 1:
            redis_client.expire(key, 60)
        if attempts > 10:
            ttl = max(redis_client.ttl(key), 0)
            raise HTTPException(status_code=429, detail=f"Too many login attempts. Try again in {ttl} seconds.")
    except RedisError:
        pass

    db_user = db.query(DbUsers).filter(DbUsers.email == email).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not db_user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    if not verify_password(form_data.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    try:
        redis_client.delete(key)
    except RedisError:
        pass

    access_token = create_access_token(db_user.id)
    refresh_token = create_refresh_token(db_user.id)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="None",
        secure=True,
        max_age=15 * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="None",
        secure=True,
        max_age=7 * 24 * 60 * 60,
    )
    return db_user


@app.post("/auth/refresh")
async def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Rotate auth tokens and blacklist the old refresh token."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    payload = verify_token(refresh_token, "refresh")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        user_id = int(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user = db.query(DbUsers).filter(DbUsers.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    key = f"blacklist:{token_hash}"

    expire_time = payload.get("exp")
    current_time = int(datetime.now(timezone.utc).timestamp())
    remaining_time = int(expire_time) - current_time
    if remaining_time <= 0:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        redis_client.setex(key, remaining_time, "blacklisted")
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Authentication service temporarily unavailable") from exc

    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        samesite="None",
        secure=True,
        max_age=15 * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        samesite="None",
        secure=True,
        max_age=7 * 24 * 60 * 60,
    )
    return {"message": "Token refreshed"}


@app.post("/auth/logout")
def logout(request: Request, response: Response):
    """Clear the auth cookies and blacklist the refresh token."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    payload = verify_token(refresh_token, "refresh")
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    key = f"blacklist:{token_hash}"

    try:
        expire_time = payload.get("exp")
        current_time = int(datetime.now(timezone.utc).timestamp())
        remaining_time = int(expire_time) - current_time
        if remaining_time <= 0:
            raise HTTPException(status_code=401, detail="Invalid token")
        redis_client.setex(key, remaining_time, "blacklisted")
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Authentication service temporarily unavailable") from exc

    response.delete_cookie("access_token", secure=True, samesite="None")
    response.delete_cookie("refresh_token", secure=True, samesite="None")
    return {"message": "Logged out"}


@app.patch("/admin/users/{user_id}/status")
def toggle_user_active(user_id: int, current_user: DbUsers = Depends(admin_required), db: Session = Depends(get_db)):
    """Enable or disable a user account."""
    user = db.query(DbUsers).filter(DbUsers.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="No user found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    user.is_active = not user.is_active
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    status = "enabled" if user.is_active else "disabled"
    return {"message": f"User {status}"}


@app.post("/checkout")
def checkout(cart: Carts = Depends(get_current_cart), current_user: DbUsers = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create an order from the current cart."""
    cart_items = cart.cart_items
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total = Decimal("0")
    for cart_item in cart_items:
        product = cart_item.product
        if cart_item.quantity > product.stock_quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        total += Decimal(cart_item.quantity) * product.price

    pending_order = (
        db.query(Orders)
        .filter(Orders.user_id == current_user.id, Orders.payment_status == PaymentStatus.PENDING)
        .first()
    )
    if pending_order:
        raise HTTPException(status_code=400, detail="Complete your existing order first.")

    order = Orders(user=current_user, total_amount=total)
    db.add(order)
    db.flush()

    for cart_item in cart_items:
        product = cart_item.product
        order_item = OrderItems(
            order=order,
            product=product,
            product_name=product.name,
            quantity=cart_item.quantity,
            price_at_purchase=product.price,
        )
        db.add(order_item)

    try:
        db.commit()
        db.refresh(order)
    except SQLAlchemyError:
        db.rollback()
        raise

    return {"order_id": order.id, "total_amount": order.total_amount, "payment_status": order.payment_status}


@app.post("/payments/create-session/{order_id}")
def create_payment(order_id: int, current_user: DbUsers = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a mock payment session for an order."""
    order = db.query(Orders).filter(Orders.id == order_id, Orders.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="No pending order")

    existing = db.query(Payments).filter(Payments.order_id == order.id, Payments.status == PaymentStatus.PENDING).first()
    if existing:
        return {"payment_id": existing.id}

    payment = Payments(order=order, amount=order.total_amount)
    db.add(payment)
    try:
        db.commit()
        db.refresh(payment)
    except SQLAlchemyError:
        db.rollback()
        raise

    return {"payment_id": payment.id, "order_id": order.id}


@app.post("/payments/mock/{payment_id}/success")
def final_payment(payment_id: int, cart: Carts = Depends(get_current_cart), current_user: DbUsers = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mark a mock payment as successful and update stock."""
    payment = db.query(Payments).filter(Payments.id == payment_id).with_for_update().first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    order = payment.order
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="Payment already processed")

    for item in order.order_items:
        product = db.query(Products).filter(Products.id == item.product_id).with_for_update().first()

        if product.stock_quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"{product.name} is out of stock.")

        product.stock_quantity -= item.quantity

    payment.status = PaymentStatus.PAID
    payment.paid_at = datetime.now(timezone.utc)
    order.payment_status = PaymentStatus.PAID
    order.status = OrderStatus.PROCESSING


    cart.cart_items.clear()

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {"message": "Payment completed successfully", "payment_id": payment.id, "order_id": order.id}