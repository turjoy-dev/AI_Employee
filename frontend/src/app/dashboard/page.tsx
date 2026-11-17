import { Suspense } from "react";

import { OverviewClient } from "./OverviewClient";

export const instant = false;

export default function DashboardOverviewPage() {
  return (
    <Suspense
      fallback={
        <div className="py-12 text-center text-sm text-[#737370]">
          Loading dashboard...
        </div>
      }
    >
      <OverviewClient />
    </Suspense>
  );
}
