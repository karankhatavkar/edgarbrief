import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

const components: Components = {
  p: ({ children }) => (
    <p className="font-serif text-[16px] leading-[1.7] mb-4 last:mb-0 text-foreground">
      {children}
    </p>
  ),
  h1: ({ children }) => (
    <h1 className="font-serif text-2xl font-bold mt-6 mb-3 leading-tight text-foreground">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="font-serif text-xl font-bold mt-5 mb-2.5 leading-tight text-foreground">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="font-serif text-lg font-semibold mt-4 mb-2 leading-tight text-foreground">
      {children}
    </h3>
  ),
  ul: ({ children }) => (
    <ul className="list-disc pl-6 mb-4 space-y-1 font-serif text-[16px] leading-[1.7] text-foreground">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-6 mb-4 space-y-1 font-serif text-[16px] leading-[1.7] text-foreground">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="leading-[1.7]">{children}</li>,
  strong: ({ children }) => <strong className="font-bold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  pre: ({ children }) => (
    <pre className="font-mono text-[13px] bg-muted p-4 rounded-lg overflow-x-auto mb-4 my-2">
      {children}
    </pre>
  ),
  code: ({ className, children, ...props }) => {
    // Language-tagged code blocks (e.g. ```python) always have a language-* class.
    // Inline code and unlabeled blocks don't. Treat labeled blocks as display code,
    // everything else as inline — the enclosing <pre> provides the visual frame.
    const isLabeledBlock = /language-/.test(className ?? "");
    if (isLabeledBlock) {
      return (
        <code className={cn("font-mono text-[13px]", className)} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code
        className="font-mono text-[0.875em] bg-muted px-1.5 py-0.5 rounded text-foreground"
        {...props}
      >
        {children}
      </code>
    );
  },
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-border pl-4 italic text-muted-foreground mb-4 font-serif text-[16px] leading-[1.7]">
      {children}
    </blockquote>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto mb-4">
      <table className="w-full border-collapse font-serif text-[15px]">
        {children}
      </table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-border px-3 py-2 bg-muted font-semibold text-left text-foreground">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-border px-3 py-2 text-foreground">{children}</td>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline underline-offset-2 hover:opacity-80"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="border-border my-6" />,
};

interface MarkdownProps {
  children: string;
  className?: string;
}

export function Markdown({ children, className }: MarkdownProps) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
