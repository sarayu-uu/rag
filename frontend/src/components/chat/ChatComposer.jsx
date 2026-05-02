/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useState } from "react";

/**
 * Detailed function explanation:
 * - Purpose: `ChatComposer` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function ChatComposer({ disabled, onSend }) {
  const [question, setQuestion] = useState("");

  /**
   * Detailed function explanation:
   * - Purpose: `submit` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
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
