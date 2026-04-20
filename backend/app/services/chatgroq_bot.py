"""
File purpose:
- Provides a minimal interactive command-line chatbot powered by ChatGroq.
- Keeps chat state in memory for the current terminal session only.
"""

'''
    to run cd backend 
    python chat_cli.py
'''

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.config.settings import GROQ_API_KEY, GROQ_MODEL


SYSTEM_PROMPT = (
    "You are a helpful assistant. Give clear, direct answers and ask for "
    "clarification only when necessary."
)


def build_chat_model() -> ChatGroq:
    if not GROQ_API_KEY:
        raise ValueError(
            "Missing GROQ_API_KEY."
        )

    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0.2,
    )


def run_cli_chatbot() -> None:
    chat_model = build_chat_model()
    history = [SystemMessage(content=SYSTEM_PROMPT)]

    print("Groq chat bot is ready.")
    print("Type your question and press Enter.")
    print("Commands: /clear to reset chat, /exit to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"/exit", "exit", "quit"}:
            print("Bye.")
            break

        if user_input.lower() == "/clear":
            history = [SystemMessage(content=SYSTEM_PROMPT)]
            print("Chat history cleared.\n")
            continue

        history.append(HumanMessage(content=user_input))

        try:
            response = chat_model.invoke(history)
        except Exception as exc:
            history.pop()
            print(f"Error: {exc}\n")
            continue

        answer = response.content if isinstance(response.content, str) else str(response.content)
        history.append(AIMessage(content=answer))
        print(f"Bot: {answer}\n")
