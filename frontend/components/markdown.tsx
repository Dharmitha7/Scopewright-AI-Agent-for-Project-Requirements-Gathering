import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Drop machine HTML comment markers; keep human-readable changelog body. */
function forDisplay(text: string): string {
  return text
    .replace(/<!--\s*\/?crewlane:draft-changelog\s*-->/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Assistant messages and documents arrive as markdown (D60); render it
// instead of showing raw asterisks (E2E finding).
export function Markdown({
  text,
  variant = "default",
}: {
  text: string;
  variant?: "default" | "document";
}) {
  const documentStyles =
    variant === "document"
      ? "[&_h2]:mt-6 [&_h2]:text-[#1e3a5f] [&_h2]:text-base [&_h3]:text-[#1e3a5f] [&_table_th]:bg-[#e8ecf1] [&_table_th]:font-semibold"
      : "";
  return (
    <div
      className={`space-y-2 text-sm leading-relaxed [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:text-sm [&_h3]:font-medium [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mt-1 [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-line [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_td]:border [&_td]:border-line [&_td]:px-2 [&_td]:py-1 [&_a]:text-accent [&_a]:underline [&_code]:rounded-sm [&_code]:bg-surface [&_code]:px-1 ${documentStyles}`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Wide tables scroll inside their own box instead of forcing the
          // whole chat pane to scroll horizontally (UX audit finding).
          table: ({ ...props }) => (
            <div className="overflow-x-auto">
              <table {...props} />
            </div>
          ),
        }}
      >
        {forDisplay(text)}
      </ReactMarkdown>
    </div>
  );
}
