"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export function Dialog({ open, onClose, title, children, footer, className = "" }: DialogProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      closeRef.current?.focus();
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  // Handle ESC close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (open) window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  // Focus trap
  useEffect(() => {
    const handleFocusTrap = (e: KeyboardEvent) => {
      if (!containerRef.current || e.key !== "Tab") return;
      const focusables = containerRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex="0"]'
      );
      if (focusables.length === 0) return;
      const first = focusables[0] as HTMLElement;
      const last = focusables[focusables.length - 1] as HTMLElement;

      if (e.shiftKey) {
        if (document.activeElement === first) {
          last.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === last) {
          first.focus();
          e.preventDefault();
        }
      }
    };
    if (open) window.addEventListener("keydown", handleFocusTrap);
    return () => window.removeEventListener("keydown", handleFocusTrap);
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog */}
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className={`
          relative w-full max-w-lg
          bg-[var(--bg-surface)] border border-[var(--bg-border)]
          rounded-[var(--radius-lg)] shadow-[var(--shadow-high)]
          flex flex-col max-h-[85vh]
          animate-in fade-in zoom-in-95 duration-[var(--duration-medium)]
          ${className}
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-[var(--space-4)] border-b border-[var(--bg-border)]">
          <h2 id="dialog-title" className="text-[1.125rem] font-bold text-[var(--text-primary)]">
            {title}
          </h2>
          <button
            ref={closeRef}
            onClick={onClose}
            className="
              p-[var(--space-2)]
              rounded-[var(--radius-md)]
              text-[var(--text-muted)]
              hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]
              transition-colors duration-[var(--duration-fast)]
              cursor-pointer
            "
            aria-label="Close dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-[var(--space-6)] text-[0.875rem] text-[var(--text-secondary)]">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-[var(--space-2)] p-[var(--space-4)] border-t border-[var(--bg-border)]">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
