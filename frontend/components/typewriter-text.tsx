"use client";

import { useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/markdown";

type Props = {
  text: string;
  /** When true, reveal as content grows (SSE). When false, show immediately. */
  animate?: boolean;
  className?: string;
};

/**
 * Stream-aware typewriter: reveals up to the full `text` length over time.
 * If `text` grows while animating (MESSAGE stream), the target extends so
 * characters keep catching up instead of restarting from scratch.
 */
export function TypewriterMarkdown({ text, animate = true, className }: Props) {
  const [shownLen, setShownLen] = useState(0);
  const targetRef = useRef(text);

  useEffect(() => {
    targetRef.current = text;
  }, [text]);

  const display = animate ? text.slice(0, Math.min(shownLen, text.length)) : text;

  useEffect(() => {
    if (!animate) return;
    const id = window.setInterval(() => {
      const target = targetRef.current;
      setShownLen((prev) => {
        if (target.length === 0) return 0;
        if (prev > target.length) return 0;
        if (prev >= target.length) return prev;
        const step = Math.max(1, Math.ceil((target.length - prev) / 24));
        return Math.min(target.length, prev + step);
      });
    }, 16);
    return () => window.clearInterval(id);
  }, [animate]);

  if (!text.trim()) return null;
  return (
    <div className={className}>
      <Markdown text={display || " "} />
    </div>
  );
}
