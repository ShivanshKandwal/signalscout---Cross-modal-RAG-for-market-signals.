import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority"
import { cn } from "../../lib/utils"

const buttonVariantsOuter = cva("transition-all duration-300 ease-in-out cursor-pointer active:scale-[0.98]", {
  variants: {
    variant: {
      primary:
        "w-full border border-black/20 dark:border-black bg-gradient-to-b from-neutral-800 to-black p-[1px]",
      accent:
        "w-full border border-pink-500/20 bg-gradient-to-b from-pink-400 to-pink-600 p-[1px]",
      secondary:
        "w-full border border-white/10 bg-neutral-800/80 p-[1px] hover:bg-neutral-800",
      minimal:
        "w-full border border-white/5 bg-neutral-900/60 p-[1px] hover:bg-neutral-800/50",
    },
    size: {
      sm: "rounded-[8px]",
      default: "rounded-[12px]",
      lg: "rounded-[14px]",
    },
  },
  defaultVariants: {
    variant: "primary",
    size: "default",
  },
})

const innerDivVariants = cva(
  "w-full h-full flex items-center justify-center font-medium gap-2 select-none",
  {
    variants: {
      variant: {
        primary:
          "bg-gradient-to-b from-neutral-700 to-neutral-950 text-white/90 shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] active:bg-neutral-950",
        accent:
          "bg-gradient-to-b from-pink-500 to-pink-700 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2)] active:bg-pink-800",
        secondary:
          "bg-gradient-to-b from-neutral-800 to-neutral-900 text-neutral-200 active:bg-neutral-900",
        minimal:
          "bg-gradient-to-b from-neutral-900 to-neutral-950 text-neutral-300 active:bg-neutral-950",
      },
      size: {
        sm: "text-xs rounded-[7px] px-3 py-1.5",
        default: "text-sm rounded-[11px] px-5 py-2.5",
        lg: "text-base rounded-[13px] px-6 py-3.5",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  }
)

const TextureButton = React.forwardRef(
  (
    {
      children,
      variant = "primary",
      size = "default",
      asChild = false,
      className,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : "button"

    return (
      <Comp
        className={cn(
          buttonVariantsOuter({ variant, size }),
          props.disabled && "opacity-40 cursor-not-allowed pointer-events-none active:scale-100",
          className
        )}
        ref={ref}
        {...props}
      >
        <div className={cn(innerDivVariants({ variant, size }))}>
          {children}
        </div>
      </Comp>
    )
  }
)
TextureButton.displayName = "TextureButton"

export { TextureButton }
