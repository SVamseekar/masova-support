"""
Agent 5: Smart Review Response
Trigger: RabbitMQ event on new review with rating <= 3
Input: review text + order details + item names + complaint keywords
Output: draft personalised manager response pushed to notification feed
Uses an LLM for a personalised response, not a template
"""
import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

DRAFT_RESPONSE_PROMPT = """You are a professional restaurant manager writing a response to a customer review.

Review: {review_text}
Rating: {rating}/5
Items ordered: {items}
Complaint keywords: {keywords}

Write a personalised, empathetic response that:
1. Acknowledges the specific feedback (mention the items if relevant)
2. Apologises sincerely without being sycophantic
3. States what action will be taken (investigate, retrain staff, improve the dish)
4. Invites the customer back with goodwill

Maximum 100 words. No marketing language. No "We value your feedback" cliches.
"""


async def draft_review_response(review_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a draft response for a low-rating review."""
    rating = review_data.get("rating", 5)
    if rating > 3:
        return {"skipped": True, "reason": "Rating > 3, no response needed"}

    from ..utils.config import get_config

    config = get_config()
    backend_url = config.backend_url

    if not config.agent_token:
        logger.warning("AGENT_TOKEN not set — review response skipped")
        return {"error": "AGENT_TOKEN not configured"}

    headers = {"Authorization": f"Bearer {config.agent_token}", "Content-Type": "application/json"}

    review_id = review_data.get("reviewId")
    rating = review_data.get("rating", 0)
    review_text = review_data.get("text", "")
    store_id = review_data.get("storeId")
    order_id = review_data.get("orderId")

    if rating > 3:
        return {"skipped": True, "reason": "Rating > 3, no response needed"}

    # Fetch order details for context
    items_str = ""
    async with httpx.AsyncClient(timeout=15.0) as client:
        if order_id:
            order_res = await client.get(f"{backend_url}/api/orders/{order_id}", headers=headers)
            if order_res.status_code == 200:
                order = order_res.json()
                items_str = ", ".join(i.get("name", "?") for i in order.get("items", []))

        # Generate response using the configured LLM
        keywords = _extract_keywords(review_text)
        prompt = DRAFT_RESPONSE_PROMPT.format(
            review_text=review_text,
            rating=rating,
            items=items_str or "unspecified items",
            keywords=", ".join(keywords) or "general dissatisfaction",
        )

        try:
            import litellm

            response = await litellm.acompletion(
                model=config.llm_model,
                api_key=config.llm_api_key,
                messages=[{"role": "user", "content": prompt}],
            )
            draft_response_text = response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("LLM call failed (%s), falling back to rule-based response", e)
            draft_response_text = _rule_based_response(review_text, rating, items_str, keywords)

        # Notify managers with the draft
        managers_res = await client.get(
            f"{backend_url}/api/users",
            params={"type": "MANAGER", "storeId": store_id},
            headers=headers,
        )

        if managers_res.status_code == 200:
            from . import _unwrap
            for manager in _unwrap(managers_res.json()):
                await client.post(
                    f"{backend_url}/api/notifications",
                    json={
                        "userId": manager["id"],
                        "type": "REVIEW_REQUEST",
                        "channel": "IN_APP",
                        "title": f"New {rating}\u2605 Review — Draft Response Ready",
                        "message": (
                            f"Review: \"{review_text[:80]}...\"\n\n"
                            f"Draft response: {draft_response_text}"
                        ),
                        "templateData": {
                            "reviewId": review_id,
                            "draftResponse": draft_response_text,
                        },
                        "priority": "HIGH" if rating == 1 else "MEDIUM",
                    },
                    headers=headers,
                )

    logger.info("Draft response generated for review %s (rating: %d)", review_id, rating)
    return {"reviewId": review_id, "draftGenerated": True, "responseLength": len(draft_response_text)}


def _extract_keywords(text: str) -> list:
    """Extract complaint keywords from review text."""
    complaint_terms = [
        "cold", "slow", "late", "wrong", "missing", "rude", "dirty",
        "overpriced", "raw", "burnt", "stale", "hair", "wait", "cancelled",
        "never arrived", "incorrect",
    ]
    text_lower = text.lower()
    return [term for term in complaint_terms if term in text_lower]


def _rule_based_response(review_text: str, rating: int, items: str, keywords: list) -> str:
    """Fallback response when the LLM call fails."""
    issue = keywords[0] if keywords else "your experience"
    item_mention = f" with {items}" if items else ""
    return (
        f"Thank you for your honest feedback. We're sorry to hear about {issue}{item_mention}. "
        f"Our team is looking into this and we'll take steps to improve. "
        f"We'd love the chance to make it right — please visit us again soon."
    )
