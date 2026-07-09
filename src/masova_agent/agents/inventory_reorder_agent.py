"""
Agent 3: Inventory Reorder
Schedule: Every 6 hours
Logic: trigger the platform's own auto-generation of purchase orders for every
       store with low-stock, auto-reorder-enabled inventory, then notify managers.
Output: POST /api/purchase-orders/auto-generate (bodyless — server groups
        low-stock items by primarySupplierId and creates one PO per supplier
        per store; client never builds the PO payload itself)
        POST /api/notifications to notify each store's managers
"""
import httpx
import logging
from datetime import datetime
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


async def run_inventory_reorder() -> Dict[str, Any]:
    """Main entry point. Returns summary of stores checked and notified."""
    from ..utils.config import get_config
    config = get_config()
    backend_url = config.backend_url

    if not config.agent_token:
        logger.warning("AGENT_TOKEN not set — inventory reorder skipped")
        return {"error": "AGENT_TOKEN not configured"}

    headers = {"Authorization": f"Bearer {config.agent_token}", "Content-Type": "application/json"}

    pos_drafted = 0
    items_checked = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        stores = await _get_stores(client, backend_url, headers)

        # Identify low-stock items per store first, purely to build the
        # manager notification message — the server does the actual PO
        # creation and supplier grouping itself.
        store_low_stock: Dict[str, List[Dict]] = {}
        for store in stores:
            store_id = store["id"]
            inv_res = await client.get(
                f"{backend_url}/api/inventory",
                params={"storeId": store_id, "lowStock": "true"},
                headers=headers,
            )
            if inv_res.status_code != 200:
                continue
            inv_items = inv_res.json()
            inv_list = (inv_items if isinstance(inv_items, list) else inv_items.get('content') or [])
            items_checked += len(inv_list)
            if inv_list:
                store_low_stock[store_id] = inv_list

        if not store_low_stock:
            logger.info("Inventory reorder complete: no low-stock items found")
            return {"pos_drafted": 0, "items_checked": items_checked}

        auto_res = await client.post(
            f"{backend_url}/api/purchase-orders/auto-generate",
            headers=headers,
        )

        if auto_res.status_code in (200, 201):
            pos_drafted = len(store_low_stock)
            for store_id, items in store_low_stock.items():
                item_names = ", ".join(i.get("itemName", "?") for i in items[:3])
                more = f" and {len(items) - 3} more" if len(items) > 3 else ""
                await _notify_manager(
                    client, backend_url, headers, store_id,
                    f"Inventory Alert: {item_names}{more} need reordering. Draft PO(s) created — please review.",
                )
        else:
            logger.warning("Auto-generate purchase orders failed: %s", auto_res.text[:120])

    logger.info("Inventory reorder complete: %d stores notified, %d items checked", pos_drafted, items_checked)
    return {"pos_drafted": pos_drafted, "items_checked": items_checked}


async def _get_stores(client: httpx.AsyncClient, backend_url: str, headers: dict) -> List[Dict]:
    res = await client.get(f"{backend_url}/api/stores", headers=headers)
    if res.status_code != 200:
        return []
    data = res.json()
    return data if isinstance(data, list) else data.get('content') or []


async def _notify_manager(
    client: httpx.AsyncClient, backend_url: str, headers: dict, store_id: str, message: str
):
    """Send notification to all managers for a store."""
    managers_res = await client.get(
        f"{backend_url}/api/users",
        params={"type": "MANAGER", "storeId": store_id},
        headers=headers,
    )
    if managers_res.status_code != 200:
        return

    managers = managers_res.json()
    for manager in ((managers if isinstance(managers, list) else managers.get('content') or [])):
        await client.post(
            f"{backend_url}/api/notifications",
            json={
                "userId": manager["id"],
                "type": "LOW_STOCK_ALERT",
                "channel": "IN_APP",
                "title": "Inventory Reorder Required",
                "message": message,
                "priority": "HIGH",
            },
            headers=headers,
        )
