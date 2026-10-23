// ===== App root + screen router + onboarding flow =====

const NAV_TABS = ['home', 'circles', 'wallet', 'profile'];

function App({ layout, palette }) {
  const [screen, setScreen] = React.useState(() => localStorage.getItem('ajo_screen') || 'home');
  const [role, setRole] = React.useState(() => localStorage.getItem('ajo_role') || 'member');
  const [onbStep, setOnbStep] = React.useState(0); // 0 welcome, 1 check a, 2 check b, 3 done

  React.useEffect(() => { localStorage.setItem('ajo_screen', screen); }, [screen]);
  React.useEffect(() => { localStorage.setItem('ajo_role', role); }, [role]);

  const nav = (k) => {
    if (k === 'new') setScreen('create');
    else setScreen(k);
  };

  // Onboarding flow
  if (screen === 'onboarding') {
    if (onbStep === 0) return <OnboardingWelcome onNext={() => setOnbStep(1)} onSkip={() => setScreen('home')} />;
    if (onbStep === 1) return <CreditCheckA onNext={() => setOnbStep(2)} onBack={() => setOnbStep(0)} />;
    if (onbStep === 2) return <CreditCheckB onNext={() => { setOnbStep(0); setScreen('home'); }} onBack={() => setOnbStep(1)} />;
  }

  // Main screens
  const showTabs = NAV_TABS.includes(screen);
  let content = null;
  if (screen === 'home') content = <Dashboard onNav={setScreen} layout={layout} role={role} />;
  else if (screen === 'circles') content = <CirclesList onNav={setScreen} />;
  else if (screen === 'wallet') content = <Wallet onNav={setScreen} />;
  else if (screen === 'profile') content = <Profile role={role} onRoleChange={setRole} />;
  else if (screen === 'circle-detail') content = <CircleDetail onBack={() => setScreen('home')} onNav={setScreen} role={role} />;
  else if (screen === 'member-profile') content = <MemberProfile onBack={() => setScreen('circle-detail')} />;
  else if (screen === 'rotation') content = <RotationView onBack={() => setScreen('circle-detail')} />;
  else if (screen === 'browse') content = <Browse onBack={() => setScreen('circles')} onNav={setScreen} />;
  else if (screen === 'join-flow') content = <Browse onBack={() => setScreen('circles')} onNav={setScreen} />;
  else if (screen === 'create') content = <CreateCircle onBack={() => setScreen('home')} onDone={() => setScreen('circle-detail')} />;
  else if (screen === 'payout') content = <PayoutFlow onBack={() => setScreen('circle-detail')} onDone={() => setScreen('home')} />;
  else if (screen === 'autoloan') content = <AutoLoan onBack={() => setScreen('home')} />;
  else if (screen === 'score') content = <ScoreDetail onBack={() => setScreen('profile')} />;
  else content = <Dashboard onNav={setScreen} layout={layout} role={role} />;

  return (
    <div className="app">
      <div style={{
        position: 'absolute', top: 10, left: 12, zIndex: 20,
        display: 'flex', gap: 6, alignItems: 'center',
      }}>
        <button className="icon-btn" onClick={() => { setScreen('onboarding'); setOnbStep(0); }}
          style={{ height: 28, width: 'auto', padding: '0 10px', fontSize: 11, color: 'var(--ink-3)', borderRadius: 999 }}
          title="Restart onboarding">
          <Icon.sparkles style={{ width: 12, height: 12 }} /> Onboarding
        </button>
      </div>
      {content}
      {showTabs && <TabBar active={screen} onNav={nav} />}
    </div>
  );
}

// Credit score detail
function ScoreDetail({ onBack }) {
  return (
    <div className="screen no-tab">
      <NavHeader title="Your credit standing" onBack={onBack} />
      <div className="section">
        <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 24 }}>
          <ScoreRing score={791} size={180} />
          <div style={{ marginTop: 14, fontSize: 13, color: 'var(--ink-3)', textAlign: 'center' }}>
            UK · Experian · updated 2 days ago
          </div>
          <div style={{ marginTop: 10, display: 'flex', gap: 6 }}>
            <span className="pill">12 mo trend: +34</span>
            <span className="pill good"><Icon.arrowUp style={{ width: 10, height: 10 }} /> Improving</span>
          </div>
        </div>
      </div>
      <div className="section" style={{ marginTop: 14 }}>
        <div className="h3" style={{ padding: '0 4px', marginBottom: 10 }}>What's working</div>
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {[
            ['Payment history', 100, 'var(--good)'],
            ['Credit utilization', 84, 'var(--brand)'],
            ['Age of accounts', 72, 'var(--accent)'],
            ['Credit mix', 55, 'var(--gold)'],
          ].map(([k, v, c], i, a) => (
            <div key={k} style={{
              padding: '14px 16px',
              borderBottom: i < a.length - 1 ? '1px solid var(--line-2)' : 'none',
            }}>
              <div className="row-between" style={{ marginBottom: 8 }}>
                <span style={{ fontSize: 13.5 }}>{k}</span>
                <span className="mono" style={{ fontSize: 13, fontWeight: 500 }}>{v}%</span>
              </div>
              <div className="bar"><span style={{ width: `${v}%`, background: c }} /></div>
            </div>
          ))}
        </div>
      </div>
      <div className="section" style={{ marginTop: 14 }}>
        <div className="card-flat" style={{ padding: 14, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          <div style={{ width: 34, height: 34, borderRadius: 10, background: 'var(--brand-soft)', color: 'var(--brand)', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
            <Icon.sparkles style={{ width: 18, height: 18 }} />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>Completing AjoCredit circles boosts your score</div>
            <div style={{ fontSize: 12.5, color: 'var(--ink-3)', marginTop: 3, lineHeight: 1.5 }}>
              We report on-time contributions to UK bureaus. Finish this cycle → est. +18 points.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { App, ScoreDetail });
