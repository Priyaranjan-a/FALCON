import { createContext, useContext, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { cn } from "@/design/cn";
import { Skeleton } from "@/design/components/Surface";
import { useLoadingMark } from "@/lib/loading";
import { remember } from "@/lib/recents";

/* The toolbar shows a compact title once the page's large title scrolls away. */
interface TitleState {
  title: ReactNode;
  compact: boolean;
}
const TitleContext = createContext<{ state: TitleState; set: (s: TitleState) => void } | null>(null);

export function PageTitleProvider({ children }: { children: ReactNode }) {
  const [state, set] = useState<TitleState>({ title: null, compact: false });
  return <TitleContext.Provider value={{ state, set }}>{children}</TitleContext.Provider>;
}

export function useToolbarTitle(): TitleState {
  return useContext(TitleContext)?.state ?? { title: null, compact: false };
}

interface PageProps {
  title: ReactNode;
  subtitle?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  width?: "standard" | "wide" | "narrow";
}

const widths = { standard: "max-w-[1180px]", wide: "max-w-[1440px]", narrow: "max-w-[860px]" };

export function Page({ title, subtitle, eyebrow, actions, children, width = "standard" }: PageProps) {
  const ctx = useContext(TitleContext);
  const heading = useRef<HTMLHeadingElement>(null);
  const setTitle = ctx?.set;

  useEffect(() => {
    const node = heading.current;
    if (!node || !setTitle) return;
    const observer = new IntersectionObserver(([entry]) => setTitle({ title, compact: !entry.isIntersecting }), { rootMargin: "-52px 0px 0px 0px" });
    observer.observe(node);
    return () => {
      observer.disconnect();
      setTitle({ title: null, compact: false });
    };
  }, [title, setTitle]);

  // The window and tab title follow the page, and the visit joins the palette's recents.
  useEffect(() => {
    if (typeof title !== "string") return;
    document.title = `${title} · FALCON`;
    remember(window.location.pathname + window.location.search, title);
    return () => {
      document.title = "FALCON";
    };
  }, [title]);

  return (
    <div className={cn("reveal mx-auto w-full px-6 pb-16 pt-6 lg:px-10", widths[width])}>
      <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          {eyebrow && <div className="mb-1 text-subhead font-medium text-label-2">{eyebrow}</div>}
          <h1 ref={heading} className="text-large-title text-label">
            {title}
          </h1>
          {subtitle && <p className="mt-1.5 max-w-[720px] text-body text-label-2">{subtitle}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </header>
      {/* A contents wrapper keeps the page's own flow; its direct children rise in sequence. */}
      <div className="reveal contents" style={{ "--reveal-base": "60ms" } as CSSProperties}>
        {children}
      </div>
    </div>
  );
}

export function PageSkeleton() {
  useLoadingMark();
  return (
    <div className="mx-auto w-full max-w-[1180px] px-6 pb-16 pt-6 lg:px-10" aria-busy="true" aria-label="Loading">
      <Skeleton className="mb-2 h-9 w-64" />
      <Skeleton className="mb-8 h-5 w-96 max-w-full" />
      <div className="grid gap-4 md:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[132px] rounded-[18px]" />
        ))}
      </div>
      <Skeleton className="mt-4 h-[320px] rounded-[18px]" />
    </div>
  );
}
