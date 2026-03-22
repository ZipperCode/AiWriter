import { cn } from "@/lib/utils"

function Separator({ className, orientation = "horizontal", ...props }: { className?: string; orientation?: "horizontal" | "vertical" } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "shrink-0 bg-border",
        orientation === "horizontal" ? "h-[1px] w-full" : "h-full w-[1px]",
        className
      )}
      {...props}
    />
  )
}

export { Separator }
