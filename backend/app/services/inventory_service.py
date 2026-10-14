from sqlalchemy.orm import Session
from typing import Optional, Tuple
from app.models.models import Cartridge, InventoryTransaction, DoseOccurrence
from app.services.clock_service import system_clock

class InventoryService:
    @staticmethod
    def decrement_stock_for_dose(
        db: Session,
        dose: DoseOccurrence,
        confirmed_pills: int,
        sensor_id: str = "sensor1_drop_counter"
    ) -> Tuple[bool, str]:
        """
        Decrements cartridge stock by the strictly sensor-confirmed count.
        Guarantees idempotency: will not decrement twice for the same dose_occurrence.
        """
        if not dose.cartridge_id:
            return False, "Dose has no cartridge assigned."

        # Idempotency check: check if already decremented for this dose
        existing_tx = db.query(InventoryTransaction).filter(
            InventoryTransaction.dose_occurrence_id == dose.id,
            InventoryTransaction.reason == "dispense_confirmed"
        ).first()

        if existing_tx:
            return False, f"Stock was already decremented by {abs(existing_tx.delta)} pills for dose {dose.id}."

        cartridge = db.query(Cartridge).filter(Cartridge.id == dose.cartridge_id).first()
        if not cartridge:
            return False, "Cartridge not found."

        if confirmed_pills <= 0:
            return False, "Zero confirmed pills to decrement."

        previous_stock = cartridge.current_stock
        new_stock = max(0, previous_stock - confirmed_pills)
        cartridge.current_stock = new_stock

        tx = InventoryTransaction(
            cartridge_id=cartridge.id,
            medication_id=dose.medication_id,
            delta=-confirmed_pills,
            previous_stock=previous_stock,
            new_stock=new_stock,
            reason="dispense_confirmed",
            confirmed_sensor_id=sensor_id,
            dose_occurrence_id=dose.id,
            timestamp=system_clock.now()
        )
        db.add(tx)
        db.commit()
        db.refresh(cartridge)

        return True, f"Stock successfully decremented from {previous_stock} to {new_stock} (-{confirmed_pills})."

    @staticmethod
    def refill_cartridge(
        db: Session,
        cartridge_number: int,
        added_pills: int,
        notes: Optional[str] = None,
        device_id: str = "ESP32_PILLBOX_01"
    ) -> Tuple[bool, str, Optional[Cartridge]]:
        cartridge = db.query(Cartridge).filter(
            Cartridge.device_id == device_id,
            Cartridge.cartridge_number == cartridge_number
        ).first()
        if not cartridge:
            return False, f"Cartridge {cartridge_number} not found on device {device_id}.", None

        if added_pills <= 0:
            return False, "Added pills must be greater than zero.", None

        previous_stock = cartridge.current_stock
        new_stock = previous_stock + added_pills
        if new_stock > cartridge.capacity:
            new_stock = cartridge.capacity

        actual_added = new_stock - previous_stock
        cartridge.current_stock = new_stock
        cartridge.last_refilled_at = system_clock.now()
        cartridge.is_configured = True

        tx = InventoryTransaction(
            cartridge_id=cartridge.id,
            medication_id=cartridge.medication_id,
            delta=actual_added,
            previous_stock=previous_stock,
            new_stock=new_stock,
            reason="refill",
            confirmed_sensor_id=None,
            dose_occurrence_id=None,
            timestamp=system_clock.now()
        )
        db.add(tx)
        db.commit()
        db.refresh(cartridge)

        return True, f"Cartridge {cartridge_number} refilled by {actual_added} pills (Total: {new_stock}).", cartridge

    @staticmethod
    def manual_stock_adjustment(
        db: Session,
        cartridge_number: int,
        new_count: int,
        reason: str = "manual_adjustment",
        device_id: str = "ESP32_PILLBOX_01"
    ) -> Tuple[bool, str, Optional[Cartridge]]:
        cartridge = db.query(Cartridge).filter(
            Cartridge.device_id == device_id,
            Cartridge.cartridge_number == cartridge_number
        ).first()
        if not cartridge:
            return False, f"Cartridge {cartridge_number} not found on device {device_id}.", None

        if new_count < 0:
            return False, "Pill count cannot be negative.", None

        previous_stock = cartridge.current_stock
        delta = new_count - previous_stock
        cartridge.current_stock = new_count
        cartridge.is_configured = True

        tx = InventoryTransaction(
            cartridge_id=cartridge.id,
            medication_id=cartridge.medication_id,
            delta=delta,
            previous_stock=previous_stock,
            new_stock=new_count,
            reason=reason,
            confirmed_sensor_id=None,
            dose_occurrence_id=None,
            timestamp=system_clock.now()
        )
        db.add(tx)
        db.commit()
        db.refresh(cartridge)

        return True, f"Cartridge {cartridge_number} count updated to {new_count}.", cartridge
