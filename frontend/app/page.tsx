import Link from "next/link";
import { ArrowRight, AudioWaveform, Blocks, ShieldCheck } from "lucide-react";
import { Brand, Vinyl } from "@/components/brand";
export default function Home() {
  return (
    <main id="main-content" className="landing">
      <nav className="landing-nav">
        <Brand />
        <div>
          <Link href="/about">서비스 소개</Link>
          <Link className="button small" href="/studio">
            음악 만들기
          </Link>
        </div>
      </nav>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">나만의 음악 만들기</p>
          <h1>
            당신의 이야기가
            <br />
            <em>음악이 되는 순간.</em>
          </h1>
          <p>
            원하는 분위기와 가사를 고르고, 내 목소리로 부르는 한 곡을 완성해 보세요.
          </p>
          <Link className="button hero-button" href="/studio">
            첫 곡 만들기 <ArrowRight />
          </Link>
          <small>처음이라도 단계별 안내를 따라 쉽게 시작할 수 있습니다.</small>
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
          title="쉬운 단계별 안내"
          text="스타일 선택부터 완성까지 한 화면에서"
        />
        <Feature
          icon={<Blocks />}
          title="나만의 가사"
          text="AI와 함께 만들거나 직접 작성"
        />
        <Feature
          icon={<ShieldCheck />}
          title="안전한 목소리 사용"
          text="본인 또는 허락받은 목소리만 사용"
        />
      </section>
      <footer className="landing-footer">
        <Brand />
        <span>웹에서 만나는 개인 음악 창작 공간</span>
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
