from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.models import Cartridge, Medication, InventoryTransaction
from app.schemas.schemas import (
    CartridgeResponse, CartridgeSetupRequest, CartridgeRefillRequest,
    CartridgeReconcileRequest, InventoryTransactionResponse
)
from app.services.inventory_service import InventoryService
from app.services.clock_service import system_clock

router = APIRouter(prefix="/cartridges", tags=["Cartridges & Inventory"])

@router.get("/", response_model=List[CartridgeResponse])
def get_cartridges(device_id: Optional[str] = None, db: Session = Depends(get_db)):
    dev_id = device_id or "ESP32_PILLBOX_01"
    from app.models.models import DeviceState
    dev = db.query(DeviceState).filter(DeviceState.device_id == dev_id).first()
    max_cart = dev.cartridge_count if dev else 4

    query = db.query(Cartridge).filter(
        Cartridge.device_id == dev_id,
        Cartridge.cartridge_number <= max_cart
    )
    cartridges = query.order_by(Cartridge.cartridge_number.asc()).all()
    results = []
    for c in cartridges:
        med = db.query(Medication).filter(Medication.id == c.medication_id).first() if c.medication_id else None
        results.append(CartridgeResponse(
            id=c.id,
            cartridge_number=c.cartridge_number,
            device_id=c.device_id,
            medication_id=c.medication_id,
            current_stock=c.current_stock,
            capacity=c.capacity,
            low_stock_threshold=c.low_stock_threshold,
            is_configured=c.is_configured,
            needs_reconciliation=bool(getattr(c, "needs_reconciliation", False)),
            quarantine_reason=getattr(c, "quarantine_reason", None),
            calibration_offset_deg=c.calibration_offset_deg,
            last_refilled_at=c.last_refilled_at,
            medication_name=med.name if med else None,
            medication_strength=med.strength if med else None,
            is_low_stock=(c.current_stock <= c.low_stock_threshold and c.is_configured)
        ))
    return results

@router.post("/setup")
def setup_cartridge(data: CartridgeSetupRequest, db: Session = Depends(get_db)):
    cart = db.query(Cartridge).filter(
        Cartridge.device_id == data.device_id,
        Cartridge.cartridge_number == data.cartridge_number
    ).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cartridge not found")

    # Safety Guard: Prevent silent reassignment when physical pills remain or slot is quarantined
    if cart.needs_reconciliation and not data.clear_reconciliation:
        raise HTTPException(
            status_code=400,
            detail=f"Cartridge {cart.cartridge_number} requires physical stock reconciliation before reassignment: {cart.quarantine_reason}. Please confirm physical clearance with clear_reconciliation=true."
        )

    if data.clear_reconciliation:
        cart.needs_reconciliation = False
        cart.quarantine_reason = None

    cart.medication_id = data.medication_id
    cart.low_stock_threshold = data.low_stock_threshold
    cart.is_configured = data.confirm_physical_loaded

    if data.initial_stock > 0:
        previous = cart.current_stock
        cart.current_stock = data.initial_stock
        cart.last_refilled_at = system_clock.now()

        tx = InventoryTransaction(
            cartridge_id=cart.id,
            medication_id=data.medication_id,
            delta=data.initial_stock - previous,
            previous_stock=previous,
            new_stock=data.initial_stock,
            reason="manual_adjustment",
            confirmed_sensor_id=None,
            dose_occurrence_id=None,
            timestamp=system_clock.now()
        )
        db.add(tx)

    db.commit()
    db.refresh(cart)
    return {"status": "success", "message": f"Cartridge {cart.cartridge_number} configured successfully."}

@router.post("/{cartridge_number}/reconcile")
def reconcile_cartridge(
    cartridge_number: int,
    data: CartridgeReconcileRequest,
    db: Session = Depends(get_db)
):
    """
    Clears the quarantine / needs-reconciliation state on a physical cartridge
    after the caregiver has physically unloaded any leftover pills.
    """
    cart = db.query(Cartridge).filter(
        Cartridge.device_id == data.device_id,
        Cartridge.cartridge_number == cartridge_number
    ).first()
    if not cart:
        raise HTTPException(status_code=404, detail=f"Cartridge {cartridge_number} not found")

    if not data.confirm_physically_empty:
        raise HTTPException(
            status_code=400,
            detail="Physical verification check is required to clear cartridge reconciliation."
        )

    prev_stock = cart.current_stock
    cart.needs_reconciliation = False
    cart.quarantine_reason = None
    cart.current_stock = 0
    cart.is_configured = False
    cart.medication_id = None

    tx = InventoryTransaction(
        cartridge_id=cart.id,
        medication_id=None,
        delta=-prev_stock if prev_stock > 0 else 0,
        previous_stock=prev_stock,
        new_stock=0,
        reason="physical_reconciliation_cleared",
        confirmed_sensor_id=None,
        dose_occurrence_id=None,
        timestamp=system_clock.now()
    )
    db.add(tx)
    db.commit()
    db.refresh(cart)

    return {
        "status": "success",
        "message": f"Cartridge {cartridge_number} physical reconciliation cleared by {data.reconciled_by}. Slot is now ready for reassignment."
    }

@router.post("/refill")
def refill_cartridge(data: CartridgeRefillRequest, db: Session = Depends(get_db)):
    cart = db.query(Cartridge).filter(
        Cartridge.device_id == data.device_id,
        Cartridge.cartridge_number == data.cartridge_number
    ).first()
    if cart and cart.needs_reconciliation:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot refill Cartridge {data.cartridge_number}: Slot is locked in stock reconciliation state ({cart.quarantine_reason}). Please clear physical reconciliation first."
        )
    success, msg, cart = InventoryService.refill_cartridge(
        db=db,
        cartridge_number=data.cartridge_number,
        added_pills=data.added_pills,
        notes=data.notes,
        device_id=data.device_id
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

@router.get("/transactions", response_model=List[InventoryTransactionResponse])
def get_inventory_transactions(limit: int = 50, db: Session = Depends(get_db)):
    txs = db.query(InventoryTransaction).order_by(InventoryTransaction.timestamp.desc()).limit(limit).all()
    results = []
    for t in txs:
        cart = db.query(Cartridge).filter(Cartridge.id == t.cartridge_id).first()
        med = db.query(Medication).filter(Medication.id == t.medication_id).first() if t.medication_id else None
        results.append(InventoryTransactionResponse(
            id=t.id,
            cartridge_id=t.cartridge_id,
            cartridge_number=cart.cartridge_number if cart else None,
            medication_name=med.name if med else "Unassigned",
            delta=t.delta,
            previous_stock=t.previous_stock,
            new_stock=t.new_stock,
            reason=t.reason,
            confirmed_sensor_id=t.confirmed_sensor_id,
            timestamp=t.timestamp
        ))
    return results
