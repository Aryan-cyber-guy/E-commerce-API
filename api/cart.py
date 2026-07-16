"""Cart endpoints and cart helper dependency."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.auth import get_current_user
from database import get_db
from db_model import CartItems, Carts, DbUsers, Products
from models import CartItemAdd, CartItemResponse, CartItemUpdate

router = APIRouter()


def get_current_cart(
    current_user: DbUsers = Depends(get_current_user), db: Session = Depends(get_db)
) -> Carts:
    """Fetch the authenticated user's cart or raise a 404."""
    cart = current_user.cart
    if not cart:
        cart = Carts(user=current_user)
        db.add(cart)

        try:
            db.commit()
            db.refresh(cart)
        except SQLAlchemyError:
            db.rollback()
            raise
    return cart


@router.get("/", response_model=list[CartItemResponse])
def get_cart_items(
    cart: Carts = Depends(get_current_cart), db: Session = Depends(get_db)
):
    """Return the current cart contents."""
    cart_items = cart.cart_items

    return [
        {
            "id": cart_item.id,
            "product_id": cart_item.product.id,
            "name": cart_item.product.name,
            "price": cart_item.product.price,
            "stock_quantity": cart_item.product.stock_quantity,
            "image_url": cart_item.product.image_url,
            "quantity": cart_item.quantity,
        }
        for cart_item in cart_items
    ]


@router.post("/items")
def add_item_to_cart(
    cart_item: CartItemAdd,
    cart: Carts = Depends(get_current_cart),
    db: Session = Depends(get_db),
):
    """Add a product to the current cart."""
    product = db.query(Products).filter(Products.id == cart_item.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing_item = (
        db.query(CartItems)
        .filter(
            CartItems.cart_id == cart.id, CartItems.product_id == cart_item.product_id
        )
        .first()
    )

    if existing_item:
        if existing_item.quantity + cart_item.quantity > product.stock_quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        existing_item.quantity += cart_item.quantity
        cart_entry = existing_item
    elif cart_item.quantity > product.stock_quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")
    else:
        cart_entry = CartItems(
            cart_id=cart.id,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
        )
        db.add(cart_entry)

    try:
        db.commit()
        db.refresh(cart_entry)
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        "message": "Item added to cart",
        "item": {
            "product_id": product.id,
            "name": product.name,
            "price": product.price,
            "stock_quantity": product.stock_quantity,
            "image_url": product.image_url,
            "quantity": cart_entry.quantity,
        },
    }


@router.patch("/items/{id}")
def update_cart_item(
    id: int,
    quantity: CartItemUpdate,
    cart: Carts = Depends(get_current_cart),
    db: Session = Depends(get_db),
):
    """Update the quantity of a cart item."""
    cart_item = (
        db.query(CartItems)
        .filter(CartItems.cart_id == cart.id, CartItems.id == id)
        .first()
    )
    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found")

    product = cart_item.product
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if quantity.quantity is None:
        raise HTTPException(status_code=400, detail="Quantity is required")
    if quantity.quantity > product.stock_quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    cart_item.quantity = quantity.quantity

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {"message": "Item updated"}


@router.delete("/items/{id}")
def delete_cart_item(
    id: int, cart: Carts = Depends(get_current_cart), db: Session = Depends(get_db)
):
    """Remove an item from the cart."""
    cart_item = (
        db.query(CartItems)
        .filter(CartItems.cart_id == cart.id, CartItems.id == id)
        .first()
    )
    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(cart_item)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {"message": "Item removed"}
