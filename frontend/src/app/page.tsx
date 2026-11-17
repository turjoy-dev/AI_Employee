"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { TOKEN_STORAGE_KEY } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const token = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    if (token) {
      router.replace("/dashboard");
    } else {
      router.replace("/login");
    }
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-700 border-t-zinc-200" />
    </main>
  );
}
