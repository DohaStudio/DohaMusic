export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand">
      <span className="brand-disc" aria-hidden="true">
        <i />
      </span>
      {!compact && (
        <span>
          <strong>DOHA MUSIC</strong>
          <small>STUDIO</small>
        </span>
      )}
    </span>
  );
}
export function Vinyl({ small = false }: { small?: boolean }) {
  return (
    <div
      className={`vinyl ${small ? "vinyl-small" : ""}`}
      aria-label="Doha Music 추상 바이닐 아트워크"
    >
      <span className="vinyl-label">D</span>
    </div>
  );
}
