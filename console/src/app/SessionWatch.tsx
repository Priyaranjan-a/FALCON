import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { toast } from "sonner";
import { onUnauthenticated } from "@/lib/api";
import { keys } from "@/lib/queries";
import type { Account } from "@/lib/types";

/**
 * When any request reports that the session ended (idle timeout, sign-out on
 * another device, suspension), drop the cached account so the router returns
 * the viewer to sign-in, with one calm notice rather than a cascade of errors.
 */
export function SessionWatch() {
  const client = useQueryClient();
  useEffect(
    () =>
      onUnauthenticated(() => {
        const account = client.getQueryData<Account | null>(keys.account);
        if (!account) return;
        client.cancelQueries();
        client.setQueryData(keys.account, null);
        toast("Your session has ended", { id: "session-ended", description: "Sign in again to continue." });
      }),
    [client],
  );
  return null;
}
