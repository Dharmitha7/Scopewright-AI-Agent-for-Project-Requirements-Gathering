import { useCallback, useEffect } from "react";

const LINE_HEIGHT_PX = 20;
const MAX_LINES = 6;

/** Grow textarea up to MAX_LINES, then scroll. */
export function useAutoResizeTextarea(
  ref: React.RefObject<HTMLTextAreaElement | null>,
  value: string,
) {
  const resize = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const max = LINE_HEIGHT_PX * MAX_LINES;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
    el.style.overflowY = el.scrollHeight > max ? "auto" : "hidden";
  }, [ref]);

  useEffect(() => {
    resize();
  }, [value, resize]);

  return resize;
}
