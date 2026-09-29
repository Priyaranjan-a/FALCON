import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { AlertDialog, Dialog } from "radix-ui";
import { useState, type ReactNode } from "react";
import { cn } from "../cn";
import { spring } from "../motion";
import { Button } from "./Button";

interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: number;
  /** Prevent closing by clicking outside (e.g. while a form is dirty). */
  modalLock?: boolean;
}

/** A centred sheet: blurred backdrop, spring entrance, sticky header and footer. */
export function Sheet({ open, onOpenChange, title, description, children, footer, width = 560, modalLock }: SheetProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild forceMount>
              <motion.div
                className="fixed inset-0 z-40 bg-[var(--overlay)] backdrop-blur-[2px]"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              />
            </Dialog.Overlay>
            <div className="pointer-events-none fixed inset-0 z-50 grid place-items-center p-4">
              <Dialog.Content
                asChild
                forceMount
                onPointerDownOutside={(e) => modalLock && e.preventDefault()}
                onInteractOutside={(e) => modalLock && e.preventDefault()}
              >
                <motion.div
                  className="glass-strong pointer-events-auto flex max-h-[min(860px,calc(100dvh-32px))] w-full flex-col overflow-hidden rounded-[22px] outline-none"
                  style={{ maxWidth: width }}
                  initial={{ opacity: 0, scale: 0.96, y: 12 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.97, y: 6, transition: { duration: 0.16 } }}
                  transition={spring.smooth}
                >
                  <header className="flex items-start gap-3 px-6 pb-3 pt-5">
                    <div className="min-w-0 flex-1">
                      <Dialog.Title className="text-title-3 text-label">{title}</Dialog.Title>
                      {description ? (
                        <Dialog.Description className="mt-1 text-subhead text-label-2">{description}</Dialog.Description>
                      ) : (
                        <Dialog.Description className="sr-only">{typeof title === "string" ? title : "Dialog"}</Dialog.Description>
                      )}
                    </div>
                    <Dialog.Close className="-mr-1.5 -mt-0.5 grid size-7 place-items-center rounded-full bg-fill text-label-2 transition-colors hover:bg-fill-hover hover:text-label focus-visible:focus-ring">
                      <X className="size-3.5" strokeWidth={2.5} />
                      <span className="sr-only">Close</span>
                    </Dialog.Close>
                  </header>
                  <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6 pt-1">{children}</div>
                  {footer && <footer className="flex items-center justify-end gap-2 px-6 py-3.5 hairline-t">{footer}</footer>}
                </motion.div>
              </Dialog.Content>
            </div>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}

interface ConfirmProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  message: ReactNode;
  confirmLabel: string;
  destructive?: boolean;
  onConfirm: () => Promise<unknown> | void;
}

/** Alert in the Apple manner: concise title, one sentence, two decisive buttons. */
export function Confirm({ open, onOpenChange, title, message, confirmLabel, destructive, onConfirm }: ConfirmProps) {
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <AlertDialog.Portal forceMount>
            <AlertDialog.Overlay asChild forceMount>
              <motion.div
                className="fixed inset-0 z-40 bg-[var(--overlay)]"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18 }}
              />
            </AlertDialog.Overlay>
            <div className="pointer-events-none fixed inset-0 z-50 grid place-items-center p-4">
              <AlertDialog.Content asChild forceMount>
                <motion.div
                  className="pointer-events-auto w-full max-w-[340px] rounded-[18px] bg-elevated p-5 text-center shadow-pop outline-none vibrancy"
                  initial={{ opacity: 0, scale: 1.08 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.14 } }}
                  transition={spring.snappy}
                >
                  <AlertDialog.Title className="text-headline text-label">{title}</AlertDialog.Title>
                  <AlertDialog.Description className="mt-1.5 text-subhead text-label-2">{message}</AlertDialog.Description>
                  <div className="mt-5 grid grid-cols-2 gap-2">
                    <AlertDialog.Cancel asChild>
                      <Button variant="gray" block disabled={busy}>
                        Cancel
                      </Button>
                    </AlertDialog.Cancel>
                    <Button variant={destructive ? "destructive" : "filled"} block loading={busy} onClick={run}>
                      {confirmLabel}
                    </Button>
                  </div>
                </motion.div>
              </AlertDialog.Content>
            </div>
          </AlertDialog.Portal>
        )}
      </AnimatePresence>
    </AlertDialog.Root>
  );
}

export function SheetSection({ title, description, children, className }: { title?: ReactNode; description?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("space-y-3 py-4 first:pt-1 [&+&]:hairline-t", className)}>
      {(title || description) && (
        <div>
          {title && <h3 className="text-headline text-label">{title}</h3>}
          {description && <p className="mt-0.5 text-subhead text-label-2">{description}</p>}
        </div>
      )}
      {children}
    </section>
  );
}
