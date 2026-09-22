/** Panel toggle (Gemini-style sidebar icon). Flip horizontally when closed. */
export function SidebarToggleIcon({ flipped = false }: { flipped?: boolean }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={flipped ? "-scale-x-100" : undefined}
      aria-hidden
    >
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
    </svg>
  );
}
