"""Source-backed specialist controls. Existing runners operate across available stores."""

SPECIALISTS = [
    {
        "name": "demand_forecast",
        "label": "Demand forecast",
        "task": "Forecast demand and plan stock",
        "route": "demand-forecast",
        "scope": "all_stores",
    },
    {
        "name": "inventory_reorder",
        "label": "Inventory reorder",
        "task": "Draft stock replenishment",
        "route": "inventory-reorder",
        "scope": "all_stores",
    },
    {
        "name": "churn_prevention",
        "label": "Churn prevention",
        "task": "Draft retention campaigns",
        "route": "churn-prevention",
        "scope": "all_stores",
    },
    {
        "name": "review_response",
        "label": "Review response",
        "task": "Draft a low-rating review reply",
        "route": "review-response",
        "scope": "review_store",
    },
    {
        "name": "shift_optimisation",
        "label": "Shift optimisation",
        "task": "Draft staffing schedules",
        "route": "shift-optimisation",
        "scope": "all_stores",
    },
    {
        "name": "kitchen_coach",
        "label": "Kitchen coach",
        "task": "Draft a kitchen coaching brief",
        "route": "kitchen-coach",
        "scope": "all_stores",
    },
    {
        "name": "dynamic_pricing",
        "label": "Dynamic pricing",
        "task": "Propose price adjustments",
        "route": "dynamic-pricing",
        "scope": "all_stores",
    },
]
