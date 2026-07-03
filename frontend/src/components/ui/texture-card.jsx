import * as React from "react"
import { cn } from "../../lib/utils"

const TextureCard = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-2xl border border-white/10 dark:border-white/5",
        "shadow-2xl overflow-hidden backdrop-blur-md",
        className
      )}
      {...props}
    >
      {/* Outer nested borders */}
      <div className="border border-black/10 dark:border-neutral-900/80 rounded-[15px]">
        <div className="border border-white/5 dark:border-neutral-950 rounded-[14px]">
          <div className="border border-neutral-950/10 dark:border-neutral-900/60 rounded-[13px]">
            {/* Inner background and styling */}
            <div className="w-full border border-white/5 dark:border-neutral-800/40 text-neutral-200 bg-gradient-to-b from-neutral-900/85 to-neutral-950/95 rounded-[12px]">
              {children}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
})
TextureCard.displayName = "TextureCard"

const TextureCardHeader = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6 pb-2", className)}
    {...props}
  />
))
TextureCardHeader.displayName = "TextureCardHeader"

const TextureCardTitle = React.forwardRef(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "text-lg font-semibold leading-none tracking-tight text-neutral-100 pl-1",
      className
    )}
    {...props}
  />
))
TextureCardTitle.displayName = "TextureCardTitle"

const TextureCardDescription = React.forwardRef(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-xs text-neutral-400 pl-1", className)}
    {...props}
  />
))
TextureCardDescription.displayName = "TextureCardDescription"

const TextureCardContent = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-2", className)} {...props} />
))
TextureCardContent.displayName = "TextureCardContent"

const TextureCardFooter = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-2 border-t border-white/5 dark:border-neutral-800/30", className)}
    {...props}
  />
))
TextureCardFooter.displayName = "TextureCardFooter"

const TextureSeparator = () => {
  return (
    <div className="border border-t-neutral-800/50 border-b-neutral-950/50 dark:border-t-neutral-900/40 dark:border-b-neutral-950/60 border-l-transparent border-r-transparent" />
  )
}

export {
  TextureCard,
  TextureCardHeader,
  TextureCardTitle,
  TextureCardDescription,
  TextureCardContent,
  TextureCardFooter,
  TextureSeparator,
}
