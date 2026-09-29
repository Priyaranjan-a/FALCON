/**
 * The desktop shell (Tauri) exposes a small global API to the console it
 * hosts. In a browser none of this exists, and every helper degrades to
 * "not available" so the same console runs in both places.
 */

interface DialogFilter {
  name: string;
  extensions: string[];
}

interface TauriGlobal {
  dialog?: {
    open(options: { directory?: boolean; multiple?: boolean; title?: string; filters?: DialogFilter[] }): Promise<string | string[] | null>;
  };
}

function bridge(): TauriGlobal | undefined {
  return (window as unknown as { __TAURI__?: TauriGlobal }).__TAURI__;
}

/** True when the console runs inside the FALCON desktop app with native dialogs. */
export function hasNativeDialogs(): boolean {
  return typeof bridge()?.dialog?.open === "function";
}

async function open(options: Parameters<NonNullable<TauriGlobal["dialog"]>["open"]>[0]): Promise<string | null> {
  const dialog = bridge()?.dialog;
  if (!dialog) return null;
  const picked = await dialog.open({ multiple: false, ...options });
  return Array.isArray(picked) ? (picked[0] ?? null) : picked;
}

export function pickFolder(title = "Choose a folder to scan"): Promise<string | null> {
  return open({ directory: true, title });
}

export function pickFile(title: string, filters: DialogFilter[]): Promise<string | null> {
  return open({ directory: false, title, filters });
}
