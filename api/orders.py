"""Order history endpoints."""

import math

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import SQLAlchemyError

from api.auth import admin_required, get_current_user
from database import get_db
from db_model import DbUsers, Orders
from models import OrderPagination, OrderDetailResponse

router = APIRouter()


def _build_order_pagination(query, page: int, size: int) -> dict:
    """Build a paginated payload for the orders query."""
    skip = (page - 1) * size
    try:
        orders = query.order_by(Orders.created_at.desc()).offset(skip).limit(size).all()
        total = query.count()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="An error occurred while fetching data from the database.",
        )
    total_pages = math.ceil(total / size) if total else 0

    return {
        "total": total,
        "page": page,
        "size": size,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": skip + size < total,
        "orders": orders,
    }


@router.get("/", response_model=OrderPagination)
def get_user_orders(
    current_user: DbUsers = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return the current user's paginated order history."""
    try:
        query = db.query(Orders).filter(Orders.user_id == current_user.id)
        return _build_order_pagination(query, page, size)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.get("/admin", response_model=OrderPagination)
def get_all_orders(
    current_user: DbUsers = Depends(admin_required),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return all orders for administrators."""
    try:
        query = db.query(Orders)
        return _build_order_pagination(query, page, size)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.get("/{id}", response_model=OrderDetailResponse)
def get_order(
    id: int,
    current_user: DbUsers = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return one active order by id."""
    order = (
        db.query(Orders)
        .options(selectinload(Orders.order_items))
        .filter(
            Orders.user_id == current_user.id,
            Orders.id == id,
        )
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


@router.get("/admin/{id}", response_model=OrderDetailResponse)
def get_specific_order(
    id: int,
    current_user: DbUsers = Depends(admin_required),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Orders)
        .options(selectinload(Orders.order_items))
        .filter(Orders.id == id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order
