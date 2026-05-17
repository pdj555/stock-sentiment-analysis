"use client";

import { motion } from "framer-motion";
import { useState } from "react";

interface TickerInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  loading: boolean;
}

export default function TickerInput({
  value,
  onChange,
  onSubmit,
  loading,
}: TickerInputProps) {
  const [focused, setFocused] = useState(false);

  return (
    <form
      className={`ticker-form${focused ? " is-focused" : ""}`}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(value);
      }}
    >
      <input
        className="ticker-input"
        value={value}
        onChange={(event) => onChange(event.target.value.toUpperCase())}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder="TICKER"
        aria-label="Stock ticker symbol"
        autoComplete="off"
        autoCapitalize="characters"
        autoCorrect="off"
        spellCheck={false}
        maxLength={12}
        disabled={loading}
        enterKeyHint="search"
      />
      <motion.button
        type="submit"
        className="ticker-submit"
        disabled={loading}
        whileTap={{ scale: 0.96 }}
      >
        {loading ? (
          <span className="spinner" aria-hidden />
        ) : (
          <>
            Analyze
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden
            >
              <path
                d="M3 8h9M8.5 3.5 13 8l-4.5 4.5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </>
        )}
      </motion.button>
    </form>
  );
}
