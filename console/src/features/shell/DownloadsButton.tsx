import { ArrowDownToLine } from "lucide-react";
import { AnimatePresence, motion, useAnimationControls } from "motion/react";
import { Popover } from "radix-ui";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Tooltip } from "@/design/components/Menu";
import { spring } from "@/design/motion";
import { useCan } from "@/lib/access";
import { onExported } from "@/lib/exports";
import { useExports } from "@/lib/queries";
import { ExportList, ExportLocationBar } from "../reports/ExportsPanel";

/**
 * Downloads, the way Safari shows them: a toolbar button that appears once
 * there is something to show, bounces when a new file lands, and opens a
 * popover with the latest exports and where they are saved.
 */
export function DownloadsButton({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const canRead = useCan("inventory.read");
  const exports = useExports();
  const navigate = useNavigate();
  const bounce = useAnimationControls();
  const [fresh, setFresh] = useState(false);
  const items = exports.data?.items ?? [];

  useEffect(
    () =>
      onExported(() => {
        setFresh(true);
        void bounce.start({ y: [0, -7, 0, -3, 0], transition: { duration: 0.7, ease: "easeOut" } });
      }),
    [bounce],
  );
  useEffect(() => {
    if (open) setFresh(false);
  }, [open]);

  if (!canRead || (!items.length && !open)) return null;

  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Tooltip content="Exports and downloads">
        <Popover.Trigger asChild>
          <motion.button
            type="button"
            aria-label="Exports and downloads"
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={spring.snappy}
            className={cn(
              "hover-light relative grid size-8 place-items-center rounded-full text-label-2 transition-colors hover:bg-fill hover:text-label focus-visible:focus-ring",
              open && "bg-fill text-label",
            )}
          >
            <motion.span animate={bounce} className="flex">
              <ArrowDownToLine className="size-[18px]" strokeWidth={1.9} />
            </motion.span>
            <AnimatePresence>
              {fresh && (
                <motion.span
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  exit={{ scale: 0 }}
                  transition={spring.snappy}
                  className="absolute right-1 top-1 size-2 rounded-full bg-accent ring-2 ring-[var(--bg)]"
                />
              )}
            </AnimatePresence>
          </motion.button>
        </Popover.Trigger>
      </Tooltip>
      <AnimatePresence>
        {open && (
          <Popover.Portal forceMount>
            <Popover.Content asChild align="end" sideOffset={8} forceMount>
              <motion.div
                initial={{ opacity: 0, scale: 0.96, y: -6 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97, transition: { duration: 0.12 } }}
                transition={spring.smooth}
                style={{ transformOrigin: "var(--radix-popover-content-transform-origin)" }}
                className="glass-strong z-50 w-[min(420px,calc(100vw-24px))] rounded-[16px] p-3 outline-none"
              >
                <div className="mb-2 flex items-center justify-between px-1">
                  <h2 className="text-headline text-label">Exports</h2>
                  <Button
                    size="sm"
                    variant="plain"
                    onClick={() => {
                      onOpenChange(false);
                      navigate("/reports#exports");
                    }}
                  >
                    Show All
                  </Button>
                </div>
                {exports.data && (
                  <div className="space-y-2">
                    <ExportList items={items} desktop={exports.data.location.desktop} limit={6} dense />
                    <ExportLocationBar location={exports.data.location} compact />
                  </div>
                )}
              </motion.div>
            </Popover.Content>
          </Popover.Portal>
        )}
      </AnimatePresence>
    </Popover.Root>
  );
}
