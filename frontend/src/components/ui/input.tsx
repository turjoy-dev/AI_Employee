import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-xl border border-[#E5E4DF] bg-[#FAFAF8] px-3.5 py-2 text-sm text-[#1A1A1A] placeholder:text-[#9A9A95] transition-colors focus-visible:outline-none focus-visible:border-[#5C8A67] focus-visible:bg-white focus-visible:ring-2 focus-visible:ring-[#5C8A67]/15 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
