import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { isoWeek } from "@/components/editorial";

/** Two-column editorial frame for sign-in, registration and password pages. */
export function AuthLayout({
  kicker,
  title,
  lede,
  children,
  footer,
}: {
  kicker: string;
  title: string;
  lede?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const { week, year } = isoWeek();
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b border-foreground">
        <div className="mx-auto w-full max-w-[1100px] px-4 md:px-8 h-12 flex items-center justify-between text-[0.8125rem]">
          <Link to="/" className="font-serif text-lg">
            Empowered Care
          </Link>
          <span className="num text-muted-foreground">
            Week {week} · {year}
          </span>
        </div>
      </header>
      <main className="flex-1 mx-auto w-full max-w-[1100px] px-4 md:px-8 py-12 md:py-20 grid md:grid-cols-12 gap-10">
        <div className="md:col-span-5">
          <p className="label-caps mb-3">{kicker}</p>
          <h1 className="text-[2.25rem] md:text-[2.75rem] leading-[1.08] font-medium">{title}</h1>
          {lede && <div className="prose-brief text-muted-foreground mt-4 max-w-md">{lede}</div>}
        </div>
        <div className="md:col-span-6 md:col-start-7">
          <div className="border-t border-foreground pt-6">{children}</div>
          {footer && <div className="mt-8 text-sm text-muted-foreground">{footer}</div>}
        </div>
      </main>
    </div>
  );
}

/** Labelled form field with optional reveal toggle for passwords. */
export function Field({
  id,
  label,
  type = "text",
  value,
  onChange,
  autoComplete,
  required = true,
  placeholder,
  hint,
}: {
  id: string;
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  required?: boolean;
  placeholder?: string;
  hint?: ReactNode;
}) {
  const [reveal, setReveal] = useState(false);
  const isPassword = type === "password";
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="label-caps">
        {label}
      </Label>
      <div className="relative">
        <Input
          id={id}
          type={isPassword && reveal ? "text" : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          required={required}
          placeholder={placeholder}
          className="h-11 text-[0.9375rem]"
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setReveal((r) => !r)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label={reveal ? "Hide password" : "Show password"}
          >
            {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
