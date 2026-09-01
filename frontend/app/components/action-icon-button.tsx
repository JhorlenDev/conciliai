"use client";

import { ButtonHTMLAttributes } from "react";
import { LucideIcon } from "lucide-react";

type ActionIconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: LucideIcon;
  label: string;
  tone?: "default" | "primary" | "success" | "danger" | "muted";
};

const toneClass = {
  default: "text-slate-700 hover:bg-slate-100",
  primary: "text-sky-800 hover:bg-sky-50",
  success: "text-emerald-800 hover:bg-emerald-50",
  danger: "text-red-700 hover:bg-red-50",
  muted: "text-slate-500 hover:bg-slate-100",
};

export function ActionIconButton({ icon: Icon, label, tone = "default", className = "", type = "button", ...props }: ActionIconButtonProps) {
  return (
    <button
      type={type}
      title={props.title ?? label}
      aria-label={props["aria-label"] ?? label}
      className={`ui-icon-button ${toneClass[tone]} ${className}`}
      {...props}
    >
      <Icon aria-hidden="true" />
    </button>
  );
}
