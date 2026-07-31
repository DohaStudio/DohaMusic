import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  TextareaHTMLAttributes,
} from "react";

export function Button({
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`button ${className}`} {...props} />;
}
export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="input" {...props} />;
}
export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className="textarea" {...props} />;
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && <small>{hint}</small>}
      {error && (
        <small role="alert" className="field-error">
          {error}
        </small>
      )}
    </div>
  );
}
export function ErrorAlert({
  title = "요청을 처리하지 못했습니다",
  message,
}: {
  title?: string;
  message: string;
}) {
  return (
    <div className="alert alert-error" role="alert">
      <strong>{title}</strong>
      <span>{message}</span>
    </div>
  );
}
export function Progress({ value, label }: { value: number; label: string }) {
  return (
    <div className="progress-wrap" aria-label={label}>
      <div className="progress-track">
        <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
      <span>{value}%</span>
    </div>
  );
}
export function Unsupported({ children }: { children: ReactNode }) {
  return (
    <button className="button secondary" disabled title="Backend API 준비 필요">
      {children} · 준비 필요
    </button>
  );
}
