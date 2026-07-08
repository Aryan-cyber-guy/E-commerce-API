"""Product catalog endpoints with basic Redis caching."""

import json
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.exceptions import RedisError
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.auth import admin_required
from database import get_db
from db_model import Category, DbUsers, Products
from models import ProductCreate, ProductPagination, ProductResponse, ProductUpdate
from redis_client import redis_client

router = APIRouter()


@router.get("/", response_model=ProductPagination)
def get_all_products(
    search: str | None = None,
    category: Category | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return a paginated list of active products."""
    cache_key = f"products:page={page}:size={size}:category={category}:search={search}"
    try:
        cached = redis_client.get(cache_key)
    except RedisError:
        cached = None

    if cached:
        return json.loads(cached)

    query = db.query(Products).filter(Products.is_active.is_(True))
    if category:
        query = query.filter(Products.category == category)
    if search:
        query = query.filter(or_(Products.name.ilike(f"%{search}%"), Products.description.ilike(f"%{search}%")))

    skip = (page - 1) * size
    products = query.order_by(Products.id).offset(skip).limit(size).all()
    total = query.count()
    total_pages = math.ceil(total / size) if total else 0

    product_response_data = {
        "total": total,
        "page": page,
        "size": size,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": skip + size < total,
        "products": products,
    }

    try:
        redis_client.setex(cache_key, 300, json.dumps(product_response_data))
    except RedisError:
        pass

    return product_response_data


@router.get("/{id}", response_model=ProductResponse)
def get_product(id: int, db: Session = Depends(get_db)):
    """Return one active product by id."""
    cache_key = f"product:{id}"
    try:
        cached = redis_client.get(cache_key)
    except RedisError:
        cached = None

    if cached:
        return json.loads(cached)

    product = db.query(Products).filter(Products.is_active.is_(True), Products.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        redis_client.setex(cache_key, 300, json.dumps(product))
    except RedisError:
        pass

    return product


@router.post("/", response_model=ProductResponse)
def add_product(product: ProductCreate, current_user: DbUsers = Depends(admin_required), db: Session = Depends(get_db)):
    """Create a new product."""
    new_product = Products(**product.model_dump())
    db.add(new_product)
    try:
        db.commit()
        db.refresh(new_product)
    except SQLAlchemyError:
        db.rollback()
        raise

    try:
        keys = list(redis_client.scan_iter("products:page=*"))
        if keys:
            redis_client.delete(*keys)
    except RedisError:
        pass

    return new_product


@router.patch("/{id}", response_model=ProductResponse)
def update_product(id: int, product: ProductUpdate, current_user: DbUsers = Depends(admin_required), db: Session = Depends(get_db)):
    """Update a product by id."""
    db_product = db.query(Products).filter(Products.id == id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    for field, value in product.model_dump(exclude_unset=True).items():
        setattr(db_product, field, value)

    try:
        db.commit()
        db.refresh(db_product)
    except SQLAlchemyError:
        db.rollback()
        raise

    try:
        keys = list(redis_client.scan_iter("products:page=*"))
        if keys:
            redis_client.delete(*keys)
        redis_client.delete(f"product:{id}")
    except RedisError:
        pass

    return db_product


@router.delete("/{id}")
def delete_product(id: int, current_user: DbUsers = Depends(admin_required), db: Session = Depends(get_db)):
    """Soft-delete a product."""
    product = db.query(Products).filter(Products.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_active = False

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    try:
        keys = list(redis_client.scan_iter("products:page=*"))
        if keys:
            redis_client.delete(*keys)
        redis_client.delete(f"product:{id}")
    except RedisError:
        pass

    return {"message": "Product is deleted"}
