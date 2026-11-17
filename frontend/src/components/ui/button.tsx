import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5C8A67]/30 disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "bg-[#5C8A67] text-white hover:bg-[#4F7A59] shadow-sm shadow-[#5C8A67]/15",
        destructive:
          "bg-[#FCECEA] text-[#B9382C] border border-[#F5C6C2] hover:bg-[#F9DEDC]",
        outline:
          "border border-[#E5E4DF] bg-white text-[#1A1A1A] hover:bg-[#F7F7F5]",
        secondary:
          "bg-[#F3F3F0] text-[#1A1A1A] hover:bg-[#EAEAE5]",
        ghost:
          "text-[#737370] hover:text-[#1A1A1A] hover:bg-[#F3F3F0]",
        link: "text-[#5C8A67] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-10 rounded-xl px-6",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
