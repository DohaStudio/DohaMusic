import Link from "next/link";
import { ArrowRight, AudioWaveform, Blocks, ShieldCheck } from "lucide-react";
import { Brand, Vinyl } from "@/components/brand";
export default function Home() {
  return (
    <main id="main-content" className="landing">
      <nav className="landing-nav">
        <Brand />
        <div>
          <Link href="/about">프로젝트</Link>
          <Link className="button small" href="/studio">
            Studio 열기
          </Link>
        </div>
      </nav>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">LOCAL-FIRST · PROVIDER-NEUTRAL</p>
          <h1>
            당신의 이야기가
            <br />
            <em>음악이 되는 순간.</em>
          </h1>
          <p>
            가사에서 목소리, 완성곡까지. 교체 가능한 AI 모듈을 하나의 추적
            가능한 Studio 흐름으로 연결합니다.
          </p>
          <Link className="button hero-button" href="/studio">
            첫 곡 만들기 <ArrowRight />
          </Link>
          <small>현재 Template Lyrics와 Mock 기반 Pipeline을 지원합니다.</small>
        </div>
        <div className="turntable">
          <div className="tonearm" />
          <Vinyl />
          <div className="turntable-label">
            <span>NOW CREATING</span>
            <strong>Doha Original</strong>
            <small>R&B · 30 sec</small>
          </div>
        </div>
      </section>
      <section className="feature-strip">
        <Feature
          icon={<AudioWaveform />}
          title="하나의 생성 흐름"
          text="설정부터 결과 metadata까지 URL로 복원"
        />
        <Feature
          icon={<Blocks />}
          title="Provider-neutral"
          text="Frontend와 AI Provider의 책임을 분리"
        />
        <Feature
          icon={<ShieldCheck />}
          title="Consent first"
          text="동의된 목소리만 Profile로 연결"
        />
      </section>
      <footer className="landing-footer">
        <Brand />
        <span>Responsive Web MVP · Native app 아님</span>
        <span>© 2026 DohaMusic</span>
      </footer>
    </main>
  );
}
function Feature({
  icon,
  title,
  text,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <article>
      {icon}
      <div>
        <h2>{title}</h2>
        <p>{text}</p>
      </div>
    </article>
  );
}
