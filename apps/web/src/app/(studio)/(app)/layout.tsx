/** Workspace layout: wraps every producer and analyst screen in the studio shell. */
import type { ReactNode } from "react";
import { Suspense } from "react";
import { Shell } from "../../../studio/shell";

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return <Suspense><Shell>{children}</Shell></Suspense>;
}
