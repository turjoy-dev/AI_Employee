import { Suspense } from "react";

import { ConversationDetailClient } from "./ConversationDetailClient";

export const instant = false;

export default function ConversationDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="py-12 text-center text-sm text-[#737370]">
          Loading transcript...
        </div>
      }
    >
      <ConversationDetailClient />
    </Suspense>
  );
}
