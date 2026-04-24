import { useState } from "react";

export default function ChatComposer({ disabled, onSend }) {
  const [question, setQuestion] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    const value = question.trim();
    if (!value || disabled) {
      return;
    }
    await onSend(value, 5);
    setQuestion("");
  };

  return (
    <form className="chat-composer" onSubmit={submit}>
      <textarea
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }}
        placeholder="Ask about indexed docs..."
        rows={3}
        disabled={disabled}
      />
      <div className="composer-row">
        <p className="muted-text composer-hint">Enter to send. Shift+Enter for new line.</p>
        <button type="submit" disabled={disabled || !question.trim()}>
          {disabled ? "Sending..." : "Send"}
        </button>
      </div>
    </form>
  );
}
