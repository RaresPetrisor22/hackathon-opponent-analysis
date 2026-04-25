"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatWidgetProps {
  /** The full dossier object that the backend uses as context. */
  dossier: Record<string, unknown>;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const API_URL =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    : "http://localhost:8000";

/* ------------------------------------------------------------------ */
/*  Markdown-lite renderer for assistant messages                      */
/* ------------------------------------------------------------------ */

/**
 * Renders a lightweight subset of markdown:
 *  - **bold**
 *  - Bullet lines (• or -)
 *  - Blank-line paragraph separation
 *  - Emoji section prefixes get a subtle highlight
 */
function renderMarkdown(text: string): React.ReactNode[] {
  const paragraphs = text.split(/\n{2,}/);

  return paragraphs.map((para, pi) => {
    const lines = para.split("\n");
    const isBulletBlock = lines.every(
      (l) => /^\s*[•\-\*]\s/.test(l) || l.trim() === ""
    );

    if (isBulletBlock) {
      const bullets = lines.filter((l) => l.trim() !== "");
      return (
        <div key={pi} style={{ margin: "6px 0" }}>
          {bullets.map((b, bi) => {
            const content = b.replace(/^\s*[•\-\*]\s*/, "");
            return (
              <div
                key={bi}
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "flex-start",
                  marginBottom: 4,
                  lineHeight: 1.55,
                }}
              >
                <span
                  style={{
                    color: "#00ff88",
                    flexShrink: 0,
                    fontWeight: 700,
                    fontSize: 10,
                    marginTop: 4,
                  }}
                >
                  ●
                </span>
                <span>{renderInline(content)}</span>
              </div>
            );
          })}
        </div>
      );
    }

    // Regular paragraph
    return (
      <p key={pi} style={{ margin: "6px 0", lineHeight: 1.6 }}>
        {lines.map((line, li) => (
          <React.Fragment key={li}>
            {li > 0 && <br />}
            {renderInline(line)}
          </React.Fragment>
        ))}
      </p>
    );
  });
}

/** Render inline markdown: **bold** */
function renderInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <strong
        key={match.index}
        style={{ color: "#00ff88", fontWeight: 600 }}
      >
        {match[1]}
      </strong>
    );
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ChatWidget({ dossier }: ChatWidgetProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Focus input when panel opens
  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const history = [...messages, userMsg];
    setMessages(history);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          dossier,
          history: messages, // send previous messages as context
        }),
      });

      if (!res.ok) {
        throw new Error(`Error ${res.status}`);
      }

      const data = await res.json();
      setMessages([...history, { role: "assistant", content: data.answer }]);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      setMessages([
        ...history,
        { role: "assistant", content: `⚠️ Failed to get a response: ${errorMessage}` },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, messages, dossier]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* ---------- Floating action button ---------- */}
      <button
        id="chat-fab"
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close chat" : "Open scouting assistant"}
        className="no-print"
        style={{
          position: "fixed",
          bottom: 28,
          right: 28,
          zIndex: 9999,
          width: 60,
          height: 60,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #00ff88 0%, #00cc6a 100%)",
          border: "none",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: open
            ? "0 0 0 4px rgba(0,255,136,.25), 0 8px 32px rgba(0,0,0,.45)"
            : "0 4px 24px rgba(0,255,136,.35), 0 8px 32px rgba(0,0,0,.4)",
          transition: "all .3s cubic-bezier(.4,0,.2,1)",
          transform: open ? "rotate(45deg)" : "rotate(0deg)",
        }}
      >
        {open ? (
          /* X icon when open */
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#0a0e1a" strokeWidth="2.5" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          /* Chat icon when closed */
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#0a0e1a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            <circle cx="9" cy="10" r="1" fill="#0a0e1a" />
            <circle cx="12" cy="10" r="1" fill="#0a0e1a" />
            <circle cx="15" cy="10" r="1" fill="#0a0e1a" />
          </svg>
        )}
      </button>

      {/* ---------- Chat panel ---------- */}
      <div
        id="chat-panel"
        className="no-print"
        style={{
          position: "fixed",
          bottom: 100,
          right: 28,
          zIndex: 9998,
          width: 420,
          maxWidth: "calc(100vw - 32px)",
          height: 560,
          maxHeight: "calc(100vh - 140px)",
          background: "#111827",
          border: "1px solid #1c2333",
          borderRadius: 16,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 20px 60px rgba(0,0,0,.6), 0 0 0 1px rgba(0,255,136,.08)",
          opacity: open ? 1 : 0,
          transform: open ? "translateY(0) scale(1)" : "translateY(20px) scale(0.95)",
          pointerEvents: open ? "auto" : "none",
          transition: "all .3s cubic-bezier(.4,0,.2,1)",
        }}
      >
        {/* ---- Header ---- */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid #1c2333",
            background: "linear-gradient(135deg, rgba(0,255,136,.06) 0%, transparent 100%)",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: "linear-gradient(135deg, #00ff88 0%, #00cc6a 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0a0e1a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: "#f9fafb", letterSpacing: "0.01em" }}>
              Scouting Assistant
            </div>
            <div style={{ fontSize: 11, color: "#9ca3af", fontFamily: "'JetBrains Mono', monospace" }}>
              Powered by dossier data
            </div>
          </div>
        </div>

        {/* ---- Messages ---- */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "16px 16px 8px",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          {messages.length === 0 && !loading && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                gap: 16,
                opacity: 0.6,
              }}
            >
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 16,
                  background: "linear-gradient(135deg, rgba(0,255,136,.12) 0%, rgba(0,255,136,.04) 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#00ff88" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <div style={{ textAlign: "center" }}>
                <p style={{ color: "#e5e7eb", fontSize: 14, fontWeight: 500, marginBottom: 4 }}>
                  Scouting Assistant
                </p>
                <p style={{ color: "#6b7280", fontSize: 12, maxWidth: 260, lineHeight: 1.5 }}>
                  Ask about tactics, key players, form, weaknesses, or any dossier insight.
                </p>
              </div>
              {/* Quick suggestion chips */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center", maxWidth: 300 }}>
                {[
                  "Key players?",
                  "Weaknesses?",
                  "Formation?",
                  "Recent form?",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => {
                      setInput(suggestion);
                      inputRef.current?.focus();
                    }}
                    style={{
                      background: "rgba(0,255,136,.08)",
                      border: "1px solid rgba(0,255,136,.15)",
                      borderRadius: 20,
                      padding: "5px 12px",
                      color: "#00ff88",
                      fontSize: 11,
                      cursor: "pointer",
                      fontFamily: "'Inter', system-ui, sans-serif",
                      transition: "all .2s",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "rgba(0,255,136,.15)";
                      e.currentTarget.style.borderColor = "rgba(0,255,136,.3)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "rgba(0,255,136,.08)";
                      e.currentTarget.style.borderColor = "rgba(0,255,136,.15)";
                    }}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                gap: 8,
                alignItems: "flex-end",
                animation: "chatFadeIn .3s ease-out",
              }}
            >
              {/* Assistant avatar */}
              {msg.role === "assistant" && (
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 8,
                    background: "linear-gradient(135deg, #00ff88 0%, #00cc6a 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    marginBottom: 2,
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0a0e1a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 20h9" />
                    <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                  </svg>
                </div>
              )}

              <div
                style={{
                  maxWidth: "80%",
                  padding: msg.role === "user" ? "10px 14px" : "12px 16px",
                  borderRadius:
                    msg.role === "user"
                      ? "14px 14px 4px 14px"
                      : "4px 14px 14px 14px",
                  background:
                    msg.role === "user"
                      ? "linear-gradient(135deg, #00ff88 0%, #00cc6a 100%)"
                      : "#1c2333",
                  color: msg.role === "user" ? "#0a0e1a" : "#e5e7eb",
                  fontSize: 13,
                  lineHeight: 1.55,
                  fontWeight: msg.role === "user" ? 500 : 400,
                  wordBreak: "break-word",
                  ...(msg.role === "assistant"
                    ? {
                        borderLeft: "2px solid rgba(0,255,136,.25)",
                      }
                    : {}),
                }}
              >
                {msg.role === "assistant"
                  ? renderMarkdown(msg.content)
                  : msg.content}
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {loading && (
            <div style={{ display: "flex", justifyContent: "flex-start", gap: 8, alignItems: "flex-end" }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 8,
                  background: "linear-gradient(135deg, #00ff88 0%, #00cc6a 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  marginBottom: 2,
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0a0e1a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 20h9" />
                  <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                </svg>
              </div>
              <div
                style={{
                  padding: "12px 18px",
                  borderRadius: "4px 14px 14px 14px",
                  background: "#1c2333",
                  borderLeft: "2px solid rgba(0,255,136,.25)",
                  display: "flex",
                  gap: 5,
                  alignItems: "center",
                }}
              >
                <span style={{ color: "#9ca3af", fontSize: 12, marginRight: 6 }}>Analyzing</span>
                {[0, 1, 2].map((j) => (
                  <span
                    key={j}
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: "#00ff88",
                      display: "inline-block",
                      animation: `chatBounce 1.2s ease-in-out infinite`,
                      animationDelay: `${j * 0.15}s`,
                    }}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ---- Input ---- */}
        <div
          style={{
            padding: "12px 16px",
            borderTop: "1px solid #1c2333",
            display: "flex",
            gap: 8,
            alignItems: "center",
            background: "rgba(17,24,39,.6)",
            backdropFilter: "blur(10px)",
          }}
        >
          <input
            ref={inputRef}
            id="chat-input"
            type="text"
            placeholder="Ask about the opponent..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            style={{
              flex: 1,
              background: "#0a0e1a",
              border: "1px solid #1c2333",
              borderRadius: 10,
              padding: "10px 14px",
              color: "#f9fafb",
              fontSize: 13,
              outline: "none",
              fontFamily: "'Inter', system-ui, sans-serif",
              transition: "border-color .2s",
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "#00ff88")}
            onBlur={(e) => (e.currentTarget.style.borderColor = "#1c2333")}
          />
          <button
            id="chat-send"
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            aria-label="Send message"
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              border: "none",
              background:
                loading || !input.trim()
                  ? "#1c2333"
                  : "linear-gradient(135deg, #00ff88 0%, #00cc6a 100%)",
              cursor: loading || !input.trim() ? "default" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all .2s",
              flexShrink: 0,
            }}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke={loading || !input.trim() ? "#4b5563" : "#0a0e1a"}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>

      {/* ---- Animations ---- */}
      <style jsx global>{`
        @keyframes chatBounce {
          0%, 60%, 100% { transform: translateY(0); opacity: .4; }
          30% { transform: translateY(-6px); opacity: 1; }
        }
        @keyframes chatFadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        #chat-panel::-webkit-scrollbar,
        #chat-panel *::-webkit-scrollbar {
          width: 4px;
        }
        #chat-panel::-webkit-scrollbar-track,
        #chat-panel *::-webkit-scrollbar-track {
          background: transparent;
        }
        #chat-panel::-webkit-scrollbar-thumb,
        #chat-panel *::-webkit-scrollbar-thumb {
          background: rgba(0,255,136,.15);
          border-radius: 4px;
        }
        #chat-panel::-webkit-scrollbar-thumb:hover,
        #chat-panel *::-webkit-scrollbar-thumb:hover {
          background: rgba(0,255,136,.3);
        }
      `}</style>
    </>
  );
}
