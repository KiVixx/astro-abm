"use client";

import { useEffect } from "react";

export function useLeaveWarning(active: boolean) {
  useEffect(() => {
    if (!active) {
      return;
    }
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [active]);
}
