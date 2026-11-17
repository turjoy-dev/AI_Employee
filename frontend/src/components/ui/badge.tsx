import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-colors tracking-tight",
  {
    variants: {
      variant: {
        default: "bg-[#F3F3F0] text-[#52524E]",
        high: "bg-[#FCECEA] text-[#B9382C]",
        medium: "bg-[#FDF0EA] text-[#C86D44]",
        low: "bg-[#F3F3F0] text-[#737370]",
        qualified: "bg-[#E6F4EA] text-[#2E7D4F]",
        converted: "bg-[#EDF3FA] text-[#3B6EA5]",
        lost: "bg-[#FCECEA] text-[#B9382C]",
        outline: "border border-[#E5E4DF] bg-white text-[#52524E]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
