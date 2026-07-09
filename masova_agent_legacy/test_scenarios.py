import os
import logging
from dotenv import load_dotenv
from agent import send_message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

def test_scenario(description: str, message: str, user_id: str = "test_user"):
    """
    Test a specific scenario with the MaSoVa agent.

    Args:
        description: Description of the test scenario
        message: The user message to send
        user_id: User identifier for the test session
    """
    print("\n" + "=" * 60)
    print(f"📋 Scenario: {description}")
    print("=" * 60)
    print(f"💬 User: {message}")

    try:
        # Each test gets its own session to avoid context pollution
        session_id = f"test_session_{description.replace(' ', '_').lower()}"
        response = send_message(message, user_id=user_id, session_id=session_id)
        print(f"\n🤖 Agent Response:\n{response}")
        print("\n✅ Test completed successfully")
        return True
    except Exception as e:
        logger.error(f"Test failed for scenario '{description}': {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("\n🧪 Running MaSoVa Agent Test Scenarios")
    print("=" * 60)

    results = []

    # Test 1: User identification and system briefing
    results.append(test_scenario(
        "User Identification",
        "Hi, I'm Soura"
    ))

    # Test 2: General menu inquiry
    results.append(test_scenario(
        "Menu Inquiry",
        "Hi, what do you have to eat today?"
    ))

    # Test 3: Specific item check
    results.append(test_scenario(
        "Item Availability",
        "Is the Pepperoni pizza available?"
    ))

    # Test 4: Order placement
    results.append(test_scenario(
        "Order Placement",
        "I'd like to order a Margherita pizza and Garlic Bread. My name is Sourav and I'm at 123 Pizza Lane."
    ))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("\n✅ All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
