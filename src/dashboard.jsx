// ===== Home / Dashboard =====

function Dashboard({ onNav, layout = 'cards', role = 'member' }) {
  const next = CIRCLE_MEMBERS.find(m => m.u === CIRCLE.recipient);
  const myPosition = CIRCLE_MEMBERS.find(m => m.me);
  const monthsToPayout = myPosition.position - CIRCLE.month;

  return (
    <>
      <TopBar sub={CIRCLE.city} />
      <div className="screen">
        {/* HERO — next payout */}
        <div className="section">
          <div className="card" style={{
            background: 'linear-gradient(135deg, var(--brand), color-mix(in srgb, var(--brand) 80%, black))',
            color: 'var(--brand-ink)', border: 0, padding: 20, position: 'relative', overflow: 'hidden',
          }}>
            <div style={{ position: 'absolute', right: -40, top: -40, width: 200, height: 200, borderRadius: '50%', background: 'rgba(255,255,255,0.06)' }} />
            <div style={{ position: 'absolute', right: 20, bottom: -60, width: 140, height: 140, borderRadius: '50%', background: 'rgba(255,255,255,0.04)' }} />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, position: 'relative' }}>
              <div className="pill" style={{ background: 'rgba(255,255,255,0.15)', color: 'var(--brand-ink)', border: 0 }}>
                <span className="dot" style={{ background: '#5AC582' }} /> Your next contribution
              </div>
              <div style={{ fontSize: 12, opacity: 0.8 }}>{CIRCLE.nextDate}</div>
            </div>

            <div style={{ position: 'relative' }}>
              <div className="mono" style={{ fontSize: 44, fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1 }}>
                £{CIRCLE.amount}
              </div>
              <div style={{ fontSize: 13.5, opacity: 0.85, marginTop: 8 }}>
                To <strong style={{ fontWeight: 500 }}>{CIRCLE.name}</strong> · auto-pays in 11 days
              </div>

              <div style={{ marginTop: 18, display: 'flex', gap: 8 }}>
                <button className="btn btn-sm" onClick={() => onNav('circle-detail')} style={{ background: 'rgba(255,255,255,0.15)', color: 'var(--brand-ink)' }}>
                  View circle
                </button>
                <button className="btn btn-sm" onClick={() => onNav('payout')} style={{ background: 'rgba(255,255,255,0.95)', color: 'var(--brand)' }}>
                  Pay early
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Today's action — next recipient */}
        <div className="section">
          <div className="card" style={{ padding: 16 }}>
            <div className="row-between" style={{ marginBottom: 12 }}>
              <div className="label-xs">This month's payout</div>
              <div className="mono muted" style={{ fontSize: 12 }}>Month {CIRCLE.month} / {CIRCLE.size}</div>
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <Avatar name={next.n} size="lg" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 15.5, fontWeight: 500 }}>{next.n} is next</div>
                <div style={{ fontSize: 12.5, color: 'var(--ink-3)', marginTop: 2 }}>@{next.u} · receives on {CIRCLE.nextDate}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="mono" style={{ fontSize: 18, fontWeight: 600 }}>£{CIRCLE.pot.toLocaleString()}</div>
                <div style={{ fontSize: 11, color: 'var(--ink-3)' }}>pot total</div>
              </div>
            </div>
            <div className="bar" style={{ marginTop: 14 }}>
              <span style={{ width: `${((CIRCLE.size - 1) / CIRCLE.size) * 100}%` }} />
            </div>
            <div className="row-between" style={{ marginTop: 8, fontSize: 12, color: 'var(--ink-3)' }}>
              <span>9 of 10 paid in</span>
              <span className="row-center"><Icon.bolt style={{ width: 12, height: 12, color: 'var(--gold)' }}/> Auto-loan armed</span>
            </div>
          </div>
        </div>

        {/* YOUR TURN strip — layouts diverge here */}
        {layout === 'cards' && <YourTurnCards monthsToPayout={monthsToPayout} myPosition={myPosition} onNav={onNav} />}
        {layout === 'timeline' && <YourTurnTimeline onNav={onNav} />}
        {layout === 'calendar' && <YourTurnCalendar myPosition={myPosition} onNav={onNav} />}

        {/* Quick actions */}
        <div className="section">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <QuickTile icon={Icon.plus} label="Join circle" sub="3 open near you" onClick={() => onNav('browse')} />
            <QuickTile icon={Icon.sparkles} label="Create circle" sub="Invite your people" onClick={() => onNav('create')} />
            <QuickTile icon={Icon.shieldPlus} label="Auto-loan" sub="Never miss a payout" onClick={() => onNav('autoloan')} accent />
            <QuickTile icon={Icon.chart} label="Your score" sub="791 · Good" onClick={() => onNav('score')} />
          </div>
        </div>

        {/* Recent activity */}
        <div className="section" style={{ marginTop: 18 }}>
          <div className="row-between" style={{ marginBottom: 10, padding: '0 4px' }}>
            <div className="h3">Activity</div>
            <button onClick={() => onNav('wallet')} style={{ fontSize: 13, color: 'var(--accent)' }}>See all</button>
          </div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {TXNS.slice(0, 3).map((t, i, a) => (
              <div key={t.id} className="row row-flat" style={{
                borderBottom: i < a.length - 1 ? '1px solid var(--line-2)' : 'none', borderRadius: 0,
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 10,
                  background: t.type === 'in' ? 'var(--good-soft)' : 'var(--surface-2)',
                  color: t.type === 'in' ? 'var(--good)' : 'var(--ink-2)',
                  display: 'grid', placeItems: 'center',
                }}>
                  {t.type === 'in' ? <Icon.arrowDown style={{ width: 16, height: 16 }} /> : <Icon.arrowUp style={{ width: 16, height: 16 }} />}
                </div>
                <div className="main">
                  <div className="title">{t.label}</div>
                  <div className="sub">{t.date} · {t.status}</div>
                </div>
                <div className="mono" style={{ fontWeight: 500, fontSize: 14, color: t.type === 'in' ? 'var(--good)' : 'var(--ink)' }}>
                  {t.type === 'in' ? '+' : '−'}£{t.amount.toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

function QuickTile({ icon: Ic, label, sub, onClick, accent }) {
  return (
    <button onClick={onClick} className="card" style={{
      textAlign: 'left', padding: 14, display: 'flex', flexDirection: 'column', gap: 10,
      background: accent ? 'var(--gold-soft)' : 'var(--surface)',
      border: accent ? '1px solid transparent' : '1px solid var(--line)',
    }}>
      <div style={{
        width: 34, height: 34, borderRadius: 10,
        background: accent ? 'var(--gold)' : 'var(--brand-soft)',
        color: accent ? '#fff' : 'var(--brand)',
        display: 'grid', placeItems: 'center',
      }}><Ic style={{ width: 18, height: 18 }} /></div>
      <div>
        <div style={{ fontWeight: 500, fontSize: 14 }}>{label}</div>
        <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 2 }}>{sub}</div>
      </div>
    </button>
  );
}

// —————— Layout A: Cards ——————
function YourTurnCards({ monthsToPayout, myPosition, onNav }) {
  return (
    <div className="section">
      <div className="row-between" style={{ marginBottom: 10, padding: '0 4px' }}>
        <div className="h3">Your turn</div>
        <div className="pill gold"><Icon.calendar style={{ width: 12, height: 12 }} /> Position #{myPosition.position}</div>
      </div>
      <div className="card" style={{ padding: 18 }}>
        <div className="serif" style={{ fontSize: 24, letterSpacing: '-0.02em', marginBottom: 4 }}>
          In {monthsToPayout} month{monthsToPayout === 1 ? '' : 's'}, you receive
        </div>
        <div className="mono" style={{ fontSize: 40, fontWeight: 600, letterSpacing: '-0.03em' }}>
          £5,000
        </div>
        <div style={{ marginTop: 14, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <div className="pill brand">Virtual account ready</div>
          <div className="pill"><Icon.check style={{ width: 12, height: 12 }} /> No bank info shared</div>
        </div>
      </div>
    </div>
  );
}

// —————— Layout B: Timeline ——————
function YourTurnTimeline({ onNav }) {
  return (
    <div className="section">
      <div className="row-between" style={{ marginBottom: 10, padding: '0 4px' }}>
        <div className="h3">Rotation timeline</div>
        <button onClick={() => onNav('rotation')} style={{ fontSize: 13, color: 'var(--accent)' }}>Full view</button>
      </div>
      <div className="card" style={{ padding: '16px 14px 16px 20px' }}>
        <div className="timeline">
          {CIRCLE_MEMBERS.slice(0, 6).map((m, i) => {
            const state = m.done ? 'done' : m.next ? 'now' : 'future';
            return (
              <div key={m.u} className={`tl-node ${state}`} style={{ paddingLeft: 10 }}>
                <div className="tl-dot" />
                <div className="card" style={{ padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 10, background: state === 'now' ? 'var(--brand-soft)' : 'var(--surface)', borderColor: state === 'now' ? 'transparent' : 'var(--line)' }}>
                  <Avatar name={m.n} size="sm" />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: 13.5 }}>{m.n} {m.me && <span className="muted">· you</span>}</div>
                    <div style={{ fontSize: 11.5, color: 'var(--ink-3)' }}>Month {m.position} · {state === 'done' ? 'received' : state === 'now' ? 'receiving now' : 'upcoming'}</div>
                  </div>
                  {state === 'now' && <div className="mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--brand)' }}>£5,000</div>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// —————— Layout C: Calendar ——————
function YourTurnCalendar({ myPosition, onNav }) {
  const months = ['Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov'];
  return (
    <div className="section">
      <div className="row-between" style={{ marginBottom: 10, padding: '0 4px' }}>
        <div className="h3">Payout calendar</div>
        <div className="pill brand">You: {months[myPosition.position - 1]}</div>
      </div>
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
          {CIRCLE_MEMBERS.sort((a, b) => a.position - b.position).map(m => {
            const state = m.done ? 'done' : m.next ? 'now' : 'future';
            return (
              <div key={m.u} style={{
                aspectRatio: '1', borderRadius: 12, padding: 8,
                background: state === 'done' ? 'var(--good-soft)' : state === 'now' ? 'var(--brand)' : 'var(--surface-2)',
                color: state === 'now' ? 'var(--brand-ink)' : 'var(--ink)',
                border: m.me ? '2px solid var(--gold)' : 'none',
                display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
              }}>
                <div style={{ fontSize: 10, opacity: 0.7, fontWeight: 500 }}>{months[m.position - 1]}</div>
                <div>
                  <div className="mono" style={{ fontSize: 11, fontWeight: 600, opacity: state === 'future' ? 0.5 : 1 }}>
                    #{m.position}
                  </div>
                  <div style={{ fontSize: 10.5, fontWeight: 500, marginTop: 2, lineHeight: 1.2, opacity: state === 'future' ? 0.7 : 1 }}>
                    {m.n.split(' ')[0]}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: 14, marginTop: 14, fontSize: 11, color: 'var(--ink-3)', flexWrap: 'wrap' }}>
          <span className="row-center"><span style={{ width: 8, height: 8, background: 'var(--good)', borderRadius: 2 }} /> Paid out</span>
          <span className="row-center"><span style={{ width: 8, height: 8, background: 'var(--brand)', borderRadius: 2 }} /> This month</span>
          <span className="row-center"><span style={{ width: 8, height: 8, border: '2px solid var(--gold)', borderRadius: 2 }} /> You</span>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Dashboard, QuickTile, YourTurnCards, YourTurnTimeline, YourTurnCalendar });
