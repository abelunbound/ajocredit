// ===== Onboarding, KYC, Credit Checks =====

function OnboardingWelcome({ onNext, onSkip }) {
  return (
    <div className="screen no-tab" style={{ padding: '30px 24px 40px', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="brandmark">
          <div className="brand-dot">a</div>
          <span>AjoCredit</span>
        </div>
        <button onClick={onSkip} className="mono" style={{ color: 'var(--ink-3)', fontSize: 12 }}>Skip demo →</button>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', paddingTop: 40 }}>
        <div className="label-xs" style={{ marginBottom: 14 }}>Community savings, done right</div>
        <h1 className="h1" style={{ fontSize: 34, lineHeight: 1.1, marginBottom: 16 }}>
          Save together, <span className="serif" style={{ fontSize: 36 }}>get paid</span> in turn.
        </h1>
        <p style={{ color: 'var(--ink-2)', fontSize: 15, lineHeight: 1.5, marginBottom: 28 }}>
          Join a trusted group of 5–10 people. Contribute £50–£800 weekly or monthly. Everyone gets a lump sum — on schedule.
        </p>

        <div style={{ display: 'grid', gap: 10, marginBottom: 24 }}>
          {[
            { icon: Icon.shield, t: 'Credit-checked members', s: 'Home-country + UK affordability' },
            { icon: Icon.bolt, t: 'Auto-payouts, on time', s: 'Interest-free backstop if someone\'s late' },
            { icon: Icon.eyeOff, t: 'Usernames only', s: 'No bank details ever shown to members' },
          ].map((f, i) => (
            <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: 4 }}>
              <div style={{
                width: 34, height: 34, borderRadius: 10,
                background: 'var(--brand-soft)', color: 'var(--brand)',
                display: 'grid', placeItems: 'center', flexShrink: 0,
              }}><f.icon style={{ width: 18, height: 18, strokeWidth: 1.8 }} /></div>
              <div>
                <div style={{ fontWeight: 500, fontSize: 14.5 }}>{f.t}</div>
                <div style={{ fontSize: 13, color: 'var(--ink-3)', marginTop: 2 }}>{f.s}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <button className="btn btn-primary btn-xl btn-block" onClick={onNext}>
        Get started
      </button>
      <button className="btn btn-block" style={{ color: 'var(--ink-2)', fontSize: 14, marginTop: 4 }} onClick={onNext}>
        I have an account
      </button>
    </div>
  );
}

// —————— Credit check A (country of origin) ——————
function CreditCheckA({ onNext, onBack }) {
  const [stage, setStage] = React.useState('intro'); // intro | running | done
  const [country, setCountry] = React.useState('Nigeria');

  React.useEffect(() => {
    if (stage === 'running') {
      const t = setTimeout(() => setStage('done'), 2200);
      return () => clearTimeout(t);
    }
  }, [stage]);

  if (stage === 'running') return <CheckRunning label={`Checking your credit in ${country}…`} onBack={onBack} />;

  if (stage === 'done') {
    return (
      <div className="screen no-tab">
        <NavHeader title="Credit check · Country of origin" onBack={onBack} />
        <div className="section" style={{ marginTop: 8 }}>
          <div className="label-xs">Result</div>
          <div className="h2" style={{ marginTop: 6, marginBottom: 16 }}>No pending debt found.</div>

          <div className="card" style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <ScoreRing score={712} tag="Good" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="label-xs">Origin: Nigeria · CRC Bureau</div>
              <div style={{ fontSize: 13, color: 'var(--ink-2)', marginTop: 8, lineHeight: 1.45 }}>
                Verified via BVN + NIN. No outstanding loans, no collections, no active judgments.
              </div>
            </div>
          </div>
        </div>

        <div className="section" style={{ marginTop: 14 }}>
          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: 0, overflow: 'hidden' }}>
            {[
              ['Active liabilities', '£0.00'],
              ['Accounts past due', '0'],
              ['Credit enquiries (12m)', '2'],
              ['Oldest account', '6 yr 4 mo'],
            ].map(([k, v], i, a) => (
              <div key={k} className="row row-flat" style={{
                padding: '14px 16px',
                borderBottom: i < a.length - 1 ? '1px solid var(--line-2)' : 'none',
                borderRadius: 0,
              }}>
                <div className="main">
                  <div style={{ fontSize: 14, color: 'var(--ink-2)' }}>{k}</div>
                </div>
                <div className="mono" style={{ fontSize: 14, fontWeight: 500 }}>{v}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ padding: '24px 20px 0' }}>
          <button className="btn btn-primary btn-xl btn-block" onClick={onNext}>
            Continue to UK check
            <Icon.arrowR style={{ width: 18, height: 18 }} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="screen no-tab">
      <NavHeader title="Credit check · a" onBack={onBack} />
      <div className="section">
        <div style={{ width: 52, height: 52, borderRadius: 14, background: 'var(--brand-soft)', color: 'var(--brand)', display: 'grid', placeItems: 'center', marginBottom: 18 }}>
          <Icon.flag style={{ width: 26, height: 26 }} />
        </div>
        <div className="label-xs">Step 2 of 4</div>
        <h2 className="h2" style={{ margin: '6px 0 8px' }}>Country of origin</h2>
        <p style={{ color: 'var(--ink-2)', fontSize: 14.5, lineHeight: 1.5, marginBottom: 24 }}>
          We'll check your credit in your country of origin to see any pending debt or liability. This never affects your UK score.
        </p>

        <div className="field" style={{ marginBottom: 14 }}>
          <label>Country of origin</label>
          <select className="input" value={country} onChange={e => setCountry(e.target.value)}>
            <option>Nigeria</option><option>Ghana</option><option>Kenya</option>
            <option>South Africa</option><option>India</option><option>Pakistan</option>
          </select>
        </div>
        <div className="field" style={{ marginBottom: 14 }}>
          <label>National identifier (BVN / NIN / equivalent)</label>
          <input className="input mono" defaultValue="2210 **** **** 4187" />
        </div>

        <div className="card-flat" style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginTop: 10, marginBottom: 24 }}>
          <Icon.lock style={{ width: 18, height: 18, color: 'var(--ink-3)', flexShrink: 0, marginTop: 2 }} />
          <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>
            Encrypted submission to accredited bureau. Soft check — no impact on your score.
          </div>
        </div>

        <button className="btn btn-primary btn-xl btn-block" onClick={() => setStage('running')}>
          Run credit check
        </button>
      </div>
    </div>
  );
}

// —————— Credit check B (UK affordability) ——————
function CreditCheckB({ onNext, onBack }) {
  const [stage, setStage] = React.useState('intro');

  React.useEffect(() => {
    if (stage === 'running') {
      const t = setTimeout(() => setStage('done'), 2200);
      return () => clearTimeout(t);
    }
  }, [stage]);

  if (stage === 'running') return <CheckRunning label="Pulling UK Experian file + Open Banking…" onBack={onBack} />;

  if (stage === 'done') {
    const afford = 1140;
    return (
      <div className="screen no-tab">
        <NavHeader title="UK credit & affordability" onBack={onBack} />
        <div className="section">
          <div className="label-xs">Result</div>
          <div className="h2" style={{ marginTop: 6, marginBottom: 16 }}>You can comfortably contribute up to <span className="mono">£{afford}</span>/mo.</div>

          <div className="card" style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <ScoreRing score={791} max={999} tag="Good" />
            <div style={{ flex: 1 }}>
              <div className="label-xs">UK · Experian</div>
              <div style={{ fontSize: 13, color: 'var(--ink-2)', marginTop: 8, lineHeight: 1.45 }}>
                7 yrs in UK · On electoral roll · 0 missed payments in 24 months.
              </div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
              <div className="h3">Affordability</div>
              <div className="mono" style={{ color: 'var(--ink-3)', fontSize: 12 }}>Last 3 months</div>
            </div>
            <AffordBar label="Net income" value={3240} max={4000} color="var(--brand)" />
            <AffordBar label="Fixed outgoings" value={1680} max={4000} color="var(--accent)" />
            <AffordBar label="Discretionary" value={420} max={4000} color="var(--gold)" />
            <div style={{ height: 1, background: 'var(--line-2)', margin: '14px 0' }} />
            <div className="row-between">
              <div style={{ fontSize: 14, color: 'var(--ink-2)' }}>Safe contribution headroom</div>
              <div className="mono" style={{ fontSize: 18, fontWeight: 600, color: 'var(--good)' }}>£{afford}</div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 14, background: 'var(--brand-soft)', border: '1px solid transparent' }}>
            <div style={{ display: 'flex', gap: 10 }}>
              <div style={{ width: 34, height: 34, borderRadius: 10, background: 'var(--brand)', color: '#fff', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <Icon.check style={{ width: 20, height: 20, strokeWidth: 2.5 }} />
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14.5, color: 'var(--brand)' }}>Eligible for all circle tiers</div>
                <div style={{ fontSize: 13, color: 'var(--ink-2)', marginTop: 3, lineHeight: 1.5 }}>
                  £50, £100, £500, £800 monthly — weekly and monthly cadences.
                </div>
              </div>
            </div>
          </div>
        </div>

        <div style={{ padding: '24px 20px 0' }}>
          <button className="btn btn-primary btn-xl btn-block" onClick={onNext}>
            Verified — finish setup
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="screen no-tab">
      <NavHeader title="Credit check · b" onBack={onBack} />
      <div className="section">
        <div style={{ width: 52, height: 52, borderRadius: 14, background: 'var(--accent-soft)', color: 'var(--accent)', display: 'grid', placeItems: 'center', marginBottom: 18 }}>
          <Icon.pound style={{ width: 26, height: 26 }} />
        </div>
        <div className="label-xs">Step 3 of 4</div>
        <h2 className="h2" style={{ margin: '6px 0 8px' }}>UK credit & affordability</h2>
        <p style={{ color: 'var(--ink-2)', fontSize: 14.5, lineHeight: 1.5, marginBottom: 20 }}>
          You've been in the UK <span style={{ color: 'var(--ink)', fontWeight: 500 }}>more than 6 months</span>, so we also run a UK check — Experian score plus a 90-day Open Banking affordability review.
        </p>

        <div className="card-flat" style={{ marginBottom: 12 }}>
          <div className="label-xs" style={{ marginBottom: 8 }}>We'll check</div>
          {[
            ['UK credit score', 'Experian hard-pull'],
            ['Affordability', 'Open Banking · 90 days'],
            ['Electoral roll', 'Address verification'],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
              <div style={{ fontSize: 14 }}>{k}</div>
              <div style={{ fontSize: 13, color: 'var(--ink-3)' }}>{v}</div>
            </div>
          ))}
        </div>

        <div className="card-flat" style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 24 }}>
          <Icon.shield style={{ width: 18, height: 18, color: 'var(--ink-3)', flexShrink: 0, marginTop: 2 }} />
          <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>
            Connect your bank securely via Truelayer. Read-only — we never move funds.
          </div>
        </div>

        <button className="btn btn-primary btn-xl btn-block" onClick={() => setStage('running')}>
          Connect bank & run check
        </button>
      </div>
    </div>
  );
}

function AffordBar({ label, value, max, color }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 13 }}>
        <span style={{ color: 'var(--ink-2)' }}>{label}</span>
        <span className="mono" style={{ fontWeight: 500 }}>£{value.toLocaleString()}</span>
      </div>
      <div className="bar" style={{ height: 8 }}>
        <span style={{ width: `${(value / max) * 100}%`, background: color }} />
      </div>
    </div>
  );
}

function CheckRunning({ label, onBack }) {
  return (
    <div className="screen no-tab">
      <NavHeader title="Running check" onBack={onBack} />
      <div style={{ padding: '60px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
        <div style={{ position: 'relative', width: 100, height: 100, marginBottom: 28 }}>
          <svg width="100" height="100" style={{ transform: 'rotate(-90deg)' }}>
            <circle cx="50" cy="50" r="44" fill="none" stroke="var(--line-2)" strokeWidth="6" />
            <circle cx="50" cy="50" r="44" fill="none" stroke="var(--brand)" strokeWidth="6"
              strokeDasharray="60 280" strokeLinecap="round" style={{ animation: 'spin 1.2s linear infinite', transformOrigin: '50% 50%' }} />
          </svg>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
        <div className="h3" style={{ marginBottom: 8 }}>{label}</div>
        <div style={{ color: 'var(--ink-3)', fontSize: 13 }}>Usually takes under a minute.</div>

        <div style={{ marginTop: 40, width: '100%', maxWidth: 320, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {['Verifying identity', 'Pulling bureau data', 'Analyzing transactions', 'Scoring'].map((step, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0' }}>
              <div className="loading-dot" style={{
                width: 10, height: 10, borderRadius: '50%',
                background: i < 2 ? 'var(--good)' : 'var(--line)',
                animationDelay: `${i * 0.15}s`,
              }} />
              <div style={{ fontSize: 13.5, color: i < 2 ? 'var(--ink)' : 'var(--ink-3)' }}>{step}</div>
              {i < 2 && <Icon.check style={{ width: 14, height: 14, color: 'var(--good)', marginLeft: 'auto' }} />}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { OnboardingWelcome, CreditCheckA, CreditCheckB, CheckRunning, AffordBar });
