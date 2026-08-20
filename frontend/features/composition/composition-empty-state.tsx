import Link from "next/link";

export function CompositionEmptyState() {
  return (
    <div className="composition-empty">
      <div>
        <p className="eyebrow">EMPTY</p>
        <h3>아직 Composition Snapshot이 없습니다.</h3>
        <p>음악 만들기에서 첫 결과를 만든 뒤 이 Project에 연결해 주세요.</p>
      </div>
      <Link className="button" href="/studio">
        음악 만들기
      </Link>
    </div>
  );
}
