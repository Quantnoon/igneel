export function Skeleton({ className = "" }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-md bg-foreground/10 ${className}`} />;
}
