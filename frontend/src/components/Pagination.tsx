import { ChevronLeft, ChevronRight } from "lucide-react";

type PaginationProps = {
  offset: number;
  limit: number;
  total: number;
  onOffsetChange: (offset: number) => void;
};

function buildPages(current: number, total: number): Array<number | "ellipsis"> {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages: Array<number | "ellipsis"> = [1];
  const windowStart = Math.max(2, current - 2);
  const windowEnd = Math.min(total - 1, current + 2);
  if (windowStart > 2) pages.push("ellipsis");
  for (let p = windowStart; p <= windowEnd; p++) pages.push(p);
  if (windowEnd < total - 1) pages.push("ellipsis");
  pages.push(total);
  return pages;
}

export function Pagination({ offset, limit, total, onOffsetChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;
  if (totalPages <= 1) return null;

  const pages = buildPages(currentPage, totalPages);
  const hasPrev = currentPage > 1;
  const hasNext = currentPage < totalPages;

  const baseBtn =
    "inline-flex h-8 min-w-[2rem] items-center justify-center rounded-sm border px-2 text-sm font-sans transition-colors";
  const inactive = "border-concrete/30 bg-paper text-ink hover:bg-manila/40";
  const active = "border-action bg-action text-paper";
  const disabledCls = "border-concrete/20 bg-paper text-concrete opacity-40 cursor-not-allowed";

  return (
    <div
      className="flex items-center justify-center gap-1.5"
      role="navigation"
      aria-label="Pagination"
    >
      <button
        type="button"
        className={`${baseBtn} ${hasPrev ? inactive : disabledCls}`}
        onClick={() => onOffsetChange((currentPage - 2) * limit)}
        disabled={!hasPrev}
        aria-label="Previous page"
      >
        <ChevronLeft size={16} />
      </button>
      {pages.map((p, idx) =>
        p === "ellipsis" ? (
          <span key={`ellipsis-${idx}`} className="px-1 text-sm text-concrete" aria-hidden="true">
            …
          </span>
        ) : (
          <button
            key={p}
            type="button"
            className={`${baseBtn} ${p === currentPage ? active : inactive}`}
            onClick={() => onOffsetChange((p - 1) * limit)}
            aria-label={`Page ${p}`}
            aria-current={p === currentPage ? "page" : undefined}
          >
            {p}
          </button>
        )
      )}
      <button
        type="button"
        className={`${baseBtn} ${hasNext ? inactive : disabledCls}`}
        onClick={() => onOffsetChange(currentPage * limit)}
        disabled={!hasNext}
        aria-label="Next page"
      >
        <ChevronRight size={16} />
      </button>
      <span className="ml-2 text-sm text-concrete">
        Page <span className="font-medium text-ink">{currentPage}</span> of {totalPages}
      </span>
    </div>
  );
}

export default Pagination;
