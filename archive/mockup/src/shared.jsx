// ===== AjoCredit shared data + components =====

// —————— Icons ——————
const Icon = {
  home: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1Z"/></svg>,
  circles: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="9" cy="9" r="5"/><circle cx="16" cy="15" r="5"/></svg>,
  wallet: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H19a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5.5A2.5 2.5 0 0 1 3 16.5Z"/><path d="M16 12.5h3"/></svg>,
  user: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="8" r="4"/><path d="M4 21c1-4.5 4.5-7 8-7s7 2.5 8 7"/></svg>,
  plus: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 5v14M5 12h14"/></svg>,
  search: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>,
  bell: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8Z"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>,
  chevR: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="m9 6 6 6-6 6"/></svg>,
  chevL: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="m15 6-6 6 6 6"/></svg>,
  check: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M5 12.5 10 17 19 7"/></svg>,
  shield: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 3 4 6v6c0 5 4 8 8 9 4-1 8-4 8-9V6Z"/><path d="m9 12 2 2 4-4"/></svg>,
  shieldPlus: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 3 4 6v6c0 5 4 8 8 9 4-1 8-4 8-9V6Z"/><path d="M12 9v6M9 12h6"/></svg>,
  bolt: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M13 3 4 14h7l-1 7 9-11h-7Z"/></svg>,
  calendar: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>,
  close: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M6 6l12 12M6 18 18 6"/></svg>,
  arrowR: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M5 12h14M13 6l6 6-6 6"/></svg>,
  arrowUp: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 19V5M5 12l7-7 7 7"/></svg>,
  arrowDown: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 5v14M19 12l-7 7-7-7"/></svg>,
  lock: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>,
  eye: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>,
  eyeOff: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="m3 3 18 18M10.5 6.3A10 10 0 0 1 22 12s-1.2 2.4-3.6 4.5M6.6 6.6C3.6 8.5 2 12 2 12s3.5 7 10 7a10 10 0 0 0 4.4-1"/><path d="M9.9 9.9A3 3 0 0 0 14 14"/></svg>,
  send: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 11 21 3l-8 18-2-8Z"/><path d="m11 13 4-4"/></svg>,
  sparkles: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/></svg>,
  dots: (p) => <svg viewBox="0 0 24 24" fill="currentColor" {...p}><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg>,
  flag: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M5 21V4h12l-2 4 2 4H5"/></svg>,
  book: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M4 4h11a3 3 0 0 1 3 3v14H7a3 3 0 0 1-3-3Z"/><path d="M4 18h14"/></svg>,
  pound: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M16 7a4 4 0 0 0-8 0v4H6m0 0h10M6 11v3c0 1.7-1 3-1 3h13"/></svg>,
  chart: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 20h18M6 16V9M11 16V5M16 16v-5M21 16v-3"/></svg>,
  alert: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="m12 3 10 18H2Z"/><path d="M12 10v5M12 18v.5"/></svg>,
};

// —————— Avatars / colors ——————
const AVATAR_PALETTES = [
  ['#0E4F47', '#3FB89B'], ['#1B6E89', '#6AA9C8'], ['#B88A2A', '#E8C468'],
  ['#7A4B2A', '#CC9461'], ['#2F7A4C', '#5AC582'], ['#8A5CB3', '#C49EEB'],
  ['#B0392E', '#E26A5D'], ['#38497A', '#7189C2'], ['#1E5C4A', '#4D9C7F'],
  ['#6B4A22', '#B08A4A'],
];
function avatarColor(name = '') {
  const i = (name.charCodeAt(0) + (name.charCodeAt(1) || 0)) % AVATAR_PALETTES.length;
  return AVATAR_PALETTES[i];
}
function Avatar({ name = '', size = 'md', style = {} }) {
  const sz = size === 'lg' ? 'avatar-lg' : size === 'xl' ? 'avatar-xl' : size === 'sm' ? 'avatar-sm' : '';
  const [a, b] = avatarColor(name);
  const initials = name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
  return (
    <div className={`avatar ${sz}`} style={{ background: `linear-gradient(135deg, ${a}, ${b})`, ...style }}>
      {initials}
    </div>
  );
}

// —————— Demo data ——————
const ME = { username: 'kemi_a', name: 'Kemi A.', city: 'Birmingham', role: 'member' };

const CIRCLE_MEMBERS = [
  { u: 'abel_o', n: 'Abel O.', next: true, paid: true, position: 3, score: 824 },
  { u: 'kemi_a', n: 'Kemi A.', paid: true, position: 4, score: 791, me: true },
  { u: 'chidi_m', n: 'Chidi M.', paid: true, position: 5, score: 765 },
  { u: 'tola_b', n: 'Tola B.', paid: true, position: 6, score: 812 },
  { u: 'nneka_o', n: 'Nneka O.', paid: true, position: 7, score: 743 },
  { u: 'daniel_k', n: 'Daniel K.', paid: 'pending', position: 8, score: 698 },
  { u: 'femi_r', n: 'Femi R.', paid: true, position: 9, score: 772 },
  { u: 'aisha_w', n: 'Aisha W.', paid: true, position: 10, score: 801 },
  { u: 'ola_t', n: 'Ola T.', done: true, position: 1, score: 818 },
  { u: 'ebuka_n', n: 'Ebuka N.', done: true, position: 2, score: 779 },
];

const CIRCLE = {
  name: 'Brum Builders',
  city: 'Birmingham, UK',
  amount: 500,
  frequency: 'monthly',
  size: 10,
  pot: 5000,
  month: 3,
  nextDate: 'Apr 28',
  recipient: 'abel_o',
  recipientName: 'Abel O.',
};

const OTHER_CIRCLES = [
  { name: 'Sister Circle', amount: 100, freq: 'weekly', size: 8, month: 4, open: false, verified: true },
  { name: 'Engineers Pool', amount: 800, freq: 'monthly', size: 6, month: 1, open: true, verified: true },
  { name: 'Lagos to UK', amount: 50, freq: 'weekly', size: 10, month: 2, open: true, verified: false },
];

const TXNS = [
  { id: 1, type: 'out', label: 'Brum Builders · April', amount: 500, date: 'Apr 1', status: 'settled' },
  { id: 2, type: 'in', label: 'Welcome bonus', amount: 10, date: 'Mar 30', status: 'settled' },
  { id: 3, type: 'out', label: 'Brum Builders · March', amount: 500, date: 'Mar 1', status: 'settled' },
  { id: 4, type: 'out', label: 'Brum Builders · February', amount: 500, date: 'Feb 1', status: 'settled' },
  { id: 5, type: 'in', label: 'Payout — Brum Builders', amount: 5000, date: 'Jan 28', status: 'queued', future: true },
];

// —————— Tab bar ——————
function TabBar({ active, onNav }) {
  const tabs = [
    { k: 'home', label: 'Home', icon: Icon.home },
    { k: 'circles', label: 'Circles', icon: Icon.circles },
    { k: 'new', label: '', icon: Icon.plus, big: true },
    { k: 'wallet', label: 'Wallet', icon: Icon.wallet },
    { k: 'profile', label: 'Profile', icon: Icon.user },
  ];
  return (
    <nav className="tabbar" data-screen-label="TabBar">
      {tabs.map(t => (
        <button
          key={t.k}
          className={`tab ${active === t.k ? 'active' : ''}`}
          onClick={() => onNav(t.k)}
        >
          {t.big ? (
            <div style={{
              width: 46, height: 46, borderRadius: 14,
              background: 'var(--brand)', color: 'var(--brand-ink)',
              display: 'grid', placeItems: 'center',
              boxShadow: '0 6px 18px color-mix(in srgb, var(--brand) 35%, transparent)',
              marginTop: -14,
            }}>
              <t.icon style={{ width: 22, height: 22 }} />
            </div>
          ) : (
            <>
              <t.icon />
              <span>{t.label}</span>
            </>
          )}
        </button>
      ))}
    </nav>
  );
}

// —————— Topbar ——————
function TopBar({ left, right, title, sub }) {
  return (
    <header className="topbar">
      {left || (
        <div className="brandmark">
          <div className="brand-dot">a</div>
          <span>{title || 'AjoCredit'}</span>
          {sub && <span style={{ color: 'var(--ink-3)', marginLeft: 4 }}>· {sub}</span>}
        </div>
      )}
      {right || (
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="icon-btn"><Icon.search style={{ width: 18, height: 18 }} /></button>
          <button className="icon-btn" style={{ position: 'relative' }}>
            <Icon.bell style={{ width: 18, height: 18 }} />
            <span style={{ position: 'absolute', top: 8, right: 9, width: 7, height: 7, background: 'var(--danger)', borderRadius: '50%', border: '1.5px solid var(--surface)' }} />
          </button>
        </div>
      )}
    </header>
  );
}

// —————— Nav header (back) ——————
function NavHeader({ title, onBack, right }) {
  return (
    <header className="topbar" style={{ paddingBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button className="icon-btn" onClick={onBack}><Icon.chevL style={{ width: 18, height: 18 }} /></button>
        <div style={{ fontWeight: 600, fontSize: 15, letterSpacing: '-0.01em' }}>{title}</div>
      </div>
      {right || <div style={{ width: 36 }} />}
    </header>
  );
}

// —————— Score ring ——————
function ScoreRing({ score, max = 999, label = 'Credit score', size = 132, tag }) {
  const pct = Math.min(1, score / max);
  const r = size / 2 - 10;
  const c = 2 * Math.PI * r;
  const band =
    score >= 780 ? 'Excellent' :
    score >= 700 ? 'Good' :
    score >= 620 ? 'Fair' : 'Poor';
  const color =
    score >= 780 ? 'var(--good)' :
    score >= 700 ? 'var(--brand)' :
    score >= 620 ? 'var(--gold)' : 'var(--danger)';
  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--line-2)" strokeWidth="8" />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${c * pct} ${c}`} strokeLinecap="round" />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center' }}>
        <div>
          <div className="label-xs" style={{ marginBottom: 2 }}>{label}</div>
          <div style={{ fontSize: 30, fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1 }} className="mono">{score}</div>
          <div style={{ marginTop: 4, fontSize: 12, fontWeight: 500, color }}>{tag || band}</div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  Icon, Avatar, avatarColor, TabBar, TopBar, NavHeader, ScoreRing,
  ME, CIRCLE, CIRCLE_MEMBERS, OTHER_CIRCLES, TXNS,
});
