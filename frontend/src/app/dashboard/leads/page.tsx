import { Suspense } from "react";

import { LeadsClient } from "./LeadsClient";

export const instant = false;

export default function LeadsPage() {
  return (
    <Suspense
      fallback={
        <div className="py-12 text-center text-sm text-[#737370]">
          Loading leads...
        </div>
      }
    >
      <LeadsClient />
    </Suspense>
  );
}
