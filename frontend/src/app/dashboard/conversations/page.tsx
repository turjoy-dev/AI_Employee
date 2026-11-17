import { Suspense } from "react";

import { ConversationsClient } from "./ConversationsClient";

export const instant = false;

export default function ConversationsPage() {
  return (
    <Suspense
      fallback={
        <div className="py-12 text-center text-sm text-[#737370]">
          Loading conversations...
        </div>
      }
    >
      <ConversationsClient />
    </Suspense>
  );
}
