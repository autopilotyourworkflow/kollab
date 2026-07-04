import type { ButtonHTMLAttributes, ReactNode } from "react"
import { cn } from "../../lib/cn"

type Variant = "primary" | "secondary" | "ghost" | "danger"
type Size = "sm" | "md"

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  leadingIcon?: ReactNode
  trailingIcon?: ReactNode
}

const base =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium " +
  "transition-[background-color,box-shadow,color,filter,transform] duration-150 ease-out " +
  "active:scale-[0.98] " + // press feedback — instant, under the 80ms perception window
  "disabled:opacity-40 disabled:pointer-events-none select-none cursor-pointer"

const variants: Record<Variant, string> = {
  primary: "bg-brand text-white shadow-xs hover:bg-brand-hover active:bg-brand-active",
  secondary:
    "bg-white text-ink border border-border-strong shadow-xs hover:bg-surface active:bg-panel",
  ghost: "bg-transparent text-ink-700 hover:bg-panel active:bg-border",
  danger: "bg-risk-high text-white shadow-xs hover:brightness-95 active:brightness-90",
}

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-10 px-4 text-sm",
}

export function Button({
  variant = "primary",
  size = "md",
  leadingIcon,
  trailingIcon,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button className={cn(base, variants[variant], sizes[size], className)} {...props}>
      {leadingIcon}
      {children}
      {trailingIcon}
    </button>
  )
}
