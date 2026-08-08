"""
Contract fixtures for MaSoVa platform backend shapes used by this service.

These capture expected field names/enums for tools — unit tests can assert
parsers tolerate both legacy and current shapes without a live backend.
"""

ORDER_STATUSES = frozenset({
    "PENDING",
    "RECEIVED",
    "PREPARING",
    "OVEN",
    "BAKED",
    "DISPATCHED",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "COMPLETED",
    "SERVED",
    "CANCELLED",
})

CANCELLABLE_STATUSES = frozenset({"PENDING", "RECEIVED"})

SAMPLE_ORDER = {
    "id": "ord-abc",
    "orderNumber": "ORD-001",
    "status": "PREPARING",
    "items": [{"quantity": 1, "name": "Margherita"}],
    "preparationTime": 20,
    "total": 12.5,
    "customerName": "Ada",
}

SAMPLE_MENU_PAGE = {
    "content": [
        {
            "name": "Margherita",
            "basePrice": 999,
            "discountedPrice": 899,
            "cuisine": "ITALIAN",
            "category": "PIZZA",
            "spiceLevel": "NONE",
            "description": "Tomato and mozzarella",
        }
    ]
}

SAMPLE_STORE_NESTED = {
    "id": "DOM001",
    "name": "MaSoVa Central",
    "status": "ACTIVE",
    "currency": "EUR",
    "locale": "en-IE",
    "operatingConfig": {"openingTime": "09:00", "closingTime": "22:00"},
}

SAMPLE_STORE_FLAT = {
    "id": "store-1",
    "name": "MaSoVa Hills",
    "isOpen": True,
    "openingTime": "09:00",
    "closingTime": "22:00",
}

SAMPLE_CUSTOMER = {
    "id": "cust-1",
    "name": "Ada",
    "loyaltyPoints": 3200,
    "loyaltyTier": "GOLD",
    "totalOrders": 42,
}

SAMPLE_REFUND_RESPONSE = {
    "refundId": "REF-1",
    "status": "PENDING_APPROVAL",
    "orderId": "ord-abc",
}

SAMPLE_CANCEL_REQUEST_RESPONSE = {
    "status": "PENDING_APPROVAL",
    "cancellationRequested": True,
}
