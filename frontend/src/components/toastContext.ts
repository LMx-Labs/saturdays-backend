import { createContext, useContext } from "react";

export type ToastTone = "success" | "error";
export type ToastContextValue = { notify: (message: string, tone?: ToastTone) => void };

export const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used inside ToastProvider");
  return value;
}
