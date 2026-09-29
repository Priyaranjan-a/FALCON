import { useAccount } from "./queries";
import type { Permission } from "./types";

/**
 * The console hides what a role cannot do, using the same permission names
 * the server enforces. Hiding is courtesy; the server remains the authority.
 */
export function useCan(permission: Permission): boolean {
  const account = useAccount();
  return !!account.data?.permissions.includes(permission);
}

export function usePermissions(): Set<Permission> {
  const account = useAccount();
  return new Set(account.data?.permissions ?? []);
}
