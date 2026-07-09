import os
import logging
from dotenv import load_dotenv
from agent import send_message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

def main():
    print("=" * 50)
    print("   MaSoVa Agent Interactive Session")
    print("=" * 50)
    print("Type 'exit' or 'quit' to end the session.\n")

    session_id = "interactive_chat_session"
    user_id = "chat_user"

    while True:
        try:
            user_input = input("\n💬 You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("\n👋 Thank you for using MaSoVa! Goodbye!")
                break

            if not user_input.strip():
                continue

            # Send message to agent
            response = send_message(user_input, user_id=user_id, session_id=session_id)
            print(f"\n🤖 MaSoVa: {response}")

        except KeyboardInterrupt:
            print("\n\n👋 Session interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            print(f"\n❌ Error: {e}")
            print("Please try again or type 'exit' to quit.")

if __name__ == "__main__":
    main()
