import { QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { RouterProvider } from "react-router";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/design/components/Menu";
import { SoundLayer } from "@/features/shell/SoundLayer";
import { queryClient } from "@/lib/queries";
import { router } from "./router";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <TooltipProvider delayDuration={450} skipDelayDuration={150}>
          <RouterProvider router={router} />
          <SoundLayer />
          <Toaster
            position="bottom-center"
            gap={8}
            toastOptions={{
              unstyled: true,
              classNames: {
                toast:
                  "flex w-[356px] items-center gap-3 rounded-[14px] bg-elevated px-4 py-3 text-subhead text-label shadow-pop vibrancy [&_[data-icon]]:shrink-0",
                title: "font-semibold",
                description: "text-label-2",
                actionButton: "ml-auto shrink-0 whitespace-nowrap rounded-[7px] bg-accent px-2.5 py-1 text-footnote font-semibold text-on-accent",
                success: "[&_[data-icon]]:text-good",
                error: "[&_[data-icon]]:text-danger",
              },
            }}
          />
        </TooltipProvider>
      </MotionConfig>
    </QueryClientProvider>
  );
}
