import {
  Alert as AlertRoot,
  AlertDescription,
} from "@/components/ui/alert";

export function Alert({ children, kind = "info", role = "status" }) {
  if (!children) return null;
  return (
    <AlertRoot variant={kind === "error" ? "destructive" : "default"} role={role}>
      <AlertDescription>{children}</AlertDescription>
    </AlertRoot>
  );
}
