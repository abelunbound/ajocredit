// ===== Circle detail, rotation, browse, create, members =====

function CircleDetail({ onBack, onNav, role = 'member' }) {
  const [tab, setTab] = React.useState('overview');
  return (
    <div className="screen no-tab">
      <NavHeader title={CIRCLE.name} onBack={onBack} right={
        <button className="icon-btn"><Icon.dots style={{ width: 18, height: 18 }} /></button>
      } />
      <div className="section">
        <div className="card" style={{ padding: 18 }}>
          <div className="label-xs">Pool · {CIRCLE.frequency}</div>
          <div className="mono" style={{ fontSize: 36, fontWeight: 600, letterSpacing: '-0.03em', marginTop: 4 }}>
            £{CIRCLE.pot.toLocaleString()}
          </div>
          <div style={{ color: 'var(--ink-3)', fontSize: 13, marginTop: 4 }}>
            £{CIRCLE.amount} × {CIRCLE.size} members · {CIRCLE.city}
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
            <div className="pill good"><Icon.shield style={{ width: 12, height: 12 }} /> Verified</div>
            <div className="pill"><Icon.bolt style={{ width: 12, height: 12, color: 'var(--gold)' }} /> Auto-loan on</div>
            <div className="pill">Month {CIRCLE.month}/{CIRCLE.size}</div>
          </div>
        </div>
      </div>

      <div className="section" style={{ marginTop: 14 }}>
        <div className="segment">
          {['overview', 'members', 'rotation'].map(t => (
            <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {tab === 'overview' && <CircleOverview onNav={onNav} role={role} />}
      {tab === 'members' && <MembersList onNav={onNav} />}
      {tab === 'rotation' && <RotationView inline />}
    </div>
  );
}

function CircleOverview({ onNav, role }) {
  return (
    <>
      <div className="section" style={{ marginTop: 14 }}>
        <div className="card" style={{ padding: 14 }}>
          <div className="row-between" style={{ marginBottom: 12 }}>
            <div className="h3">This month's payout</div>
            <div className="mono muted" style={{ fontSize: 12 }}>{CIRCLE.nextDate}</div>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <Avatar name={CIRCLE.recipientName} size="lg" />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 500 }}>{CIRCLE.recipientName}</div>
              <div style={{ fontSize: 12.5, color: 'var(--ink-3)' }}>@{CIRCLE.recipient}</div>
            </div>
            <div className="mono" style={{ fontSize: 18, fontWeight: 600 }}>£{CIRCLE.pot.toLocaleString()}</div>
          </div>
          <div style={{ height: 1, background: 'var(--line-2)', margin: '14px 0' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <div style={{ color: 'var(--ink-3)' }}>Contributions in</div>
            <div className="mono" style={{ fontWeight: 500 }}>9 of 10 · £4,500</div>
          </div>
          <div className="bar" style={{ marginTop: 8 }}>
            <span style={{ width: '90%' }} />
          </div>
          {role === 'admin' && (
            <button className="btn btn-primary btn-block" style={{ marginTop: 14 }} onClick={() => onNav('payout')}>
              Review & release payout
            </button>
          )}
        </div>
      </div>

      <div className="section" style={{ marginTop: 14 }}>
        <div className="h3" style={{ padding: '0 4px', marginBottom: 10 }}>Safety</div>
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <button className="row" onClick={() => onNav('autoloan')} style={{ width: '100%', border: 0, borderRadius: 0, background: 'transparent', padding: '14px 16px' }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'var(--gold-soft)', color: 'var(--gold)', display: 'grid', placeItems: 'center' }}>
              <Icon.bolt style={{ width: 18, height: 18 }} />
            </div>
            <div className="main" style={{ textAlign: 'left' }}>
              <div className="title">Auto-loan backstop</div>
              <div className="sub">Interest-free · covers up to 1 missed contribution</div>
            </div>
            <Icon.chevR style={{ width: 16, height: 16, color: 'var(--ink-4)' }} />
          </button>
          <div style={{ height: 1, background: 'var(--line-2)' }} />
          <button className="row" style={{ width: '100%', border: 0, borderRadius: 0, background: 'transparent', padding: '14px 16px' }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'var(--brand-soft)', color: 'var(--brand)', display: 'grid', placeItems: 'center' }}>
              <Icon.shield style={{ width: 18, height: 18 }} />
            </div>
            <div className="main" style={{ textAlign: 'left' }}>
              <div className="title">All 10 members credit-checked</div>
              <div className="sub">Min score 680 · affordability verified</div>
            </div>
            <Icon.chevR style={{ width: 16, height: 16, color: 'var(--ink-4)' }} />
          </button>
        </div>
      </div>

      <div className="section" style={{ marginTop: 14, marginBottom: 20 }}>
        <div className="h3" style={{ padding: '0 4px', marginBottom: 10 }}>Circle rules</div>
        <div className="card-flat" style={{ padding: 16 }}>
          {[
            ['Contribution', `£${CIRCLE.amount} monthly · autopay on the 1st`],
            ['Rotation', 'Order set by join-date · unchanged mid-cycle'],
            ['Late grace', '48 hours before auto-loan activates'],
            ['Exit', 'Only after your payout month'],
          ].map(([k, v], i, a) => (
            <div key={k} style={{ padding: '10px 0', borderBottom: i < a.length - 1 ? '1px solid var(--line-2)' : 'none' }}>
              <div style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3 }}>{k}</div>
              <div style={{ fontSize: 13.5 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function MembersList({ onNav }) {
  return (
    <div className="section" style={{ marginTop: 14 }}>
      <div className="label-xs" style={{ marginBottom: 10 }}>{CIRCLE.size} members · usernames only</div>
      <div className="card" style={{ padding: '4px 16px' }}>
        {CIRCLE_MEMBERS.sort((a, b) => a.position - b.position).map((m, i, a) => (
          <button key={m.u} onClick={() => onNav('member-profile')}
            className="row row-flat" style={{
              width: '100%', textAlign: 'left',
              borderBottom: i < a.length - 1 ? '1px solid var(--line-2)' : 'none',
              borderRadius: 0,
            }}>
            <Avatar name={m.n} />
            <div className="main">
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <div className="title">@{m.u}</div>
                {m.me && <span className="pill brand" style={{ height: 20, fontSize: 11 }}>you</span>}
                {m.next && <span className="pill gold" style={{ height: 20, fontSize: 11 }}>next</span>}
              </div>
              <div className="sub">
                {m.done ? 'Received month ' + m.position : m.next ? `Receives month ${m.position}` : `Position #${m.position}`}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="mono" style={{ fontSize: 12, color: m.paid === 'pending' ? 'var(--gold)' : m.paid || m.done ? 'var(--good)' : 'var(--ink-3)' }}>
                {m.done ? 'past' : m.paid === 'pending' ? '· pending' : m.paid ? '✓ paid' : ''}
              </div>
              <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 2 }}>score {m.score}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function RotationView({ onBack, onNav, inline = false }) {
  const content = (
    <div className="section" style={{ marginTop: 14 }}>
      <div className="timeline">
        {CIRCLE_MEMBERS.sort((a, b) => a.position - b.position).map(m => {
          const state = m.done ? 'done' : m.next ? 'now' : 'future';
          return (
            <div key={m.u} className={`tl-node ${state}`} style={{ paddingLeft: 10 }}>
              <div className="tl-dot" />
              <div className="card" style={{
                padding: '12px 14px',
                background: state === 'now' ? 'var(--brand-soft)' : state === 'done' ? 'var(--surface-2)' : 'var(--surface)',
                borderColor: state === 'now' ? 'transparent' : 'var(--line)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Avatar name={m.n} size="sm" />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <div style={{ fontWeight: 500, fontSize: 14 }}>{m.n}</div>
                      {m.me && <span className="pill brand" style={{ height: 18, fontSize: 10, padding: '0 6px' }}>you</span>}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 1 }}>
                      Month {m.position} {state === 'done' && '· paid'} {state === 'now' && `· ${CIRCLE.nextDate}`}
                    </div>
                  </div>
                  <div className="mono" style={{
                    fontSize: 14, fontWeight: 600,
                    color: state === 'now' ? 'var(--brand)' : state === 'done' ? 'var(--good)' : 'var(--ink-3)',
                  }}>£{CIRCLE.pot.toLocaleString()}</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
  if (inline) return content;
  return (
    <div className="screen no-tab">
      <NavHeader title="Rotation" onBack={onBack} />
      {content}
    </div>
  );
}

// ============ Browse / Join ============
function Browse({ onBack, onNav }) {
  return (
    <div className="screen">
      <NavHeader title="Find a circle" onBack={onBack} right={
        <button className="icon-btn"><Icon.search style={{ width: 18, height: 18 }} /></button>
      } />
      <div className="section">
        <div className="segment" style={{ marginBottom: 14 }}>
          <button className="on">Nearby</button>
          <button>Invite only</button>
          <button>My matches</button>
        </div>
        <div style={{ display: 'grid', gap: 12 }}>
          {OTHER_CIRCLES.map((c, i) => (
            <button key={i} onClick={() => onNav('join-flow')} className="card" style={{ textAlign: 'left', padding: 16 }}>
              <div className="row-between" style={{ marginBottom: 6 }}>
                <div style={{ fontSize: 15, fontWeight: 600 }}>{c.name}</div>
                {c.verified && <div className="pill good"><Icon.check style={{ width: 12, height: 12 }} /> Verified</div>}
              </div>
              <div style={{ fontSize: 13, color: 'var(--ink-3)', marginBottom: 12 }}>
                £{c.amount} {c.freq} · {c.size} members · {c.open ? 'Accepting members' : 'Full'}
              </div>
              <div className="row-between">
                <div style={{ display: 'flex' }}>
                  {[0,1,2,3].map(j => (
                    <Avatar key={j} name={'ABCD'[j] + 'x'} size="sm" style={{ marginLeft: j === 0 ? 0 : -8, border: '2px solid var(--surface)' }} />
                  ))}
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%',
                    background: 'var(--surface-2)', border: '2px solid var(--surface)',
                    marginLeft: -8, display: 'grid', placeItems: 'center',
                    fontSize: 10, color: 'var(--ink-3)', fontWeight: 500,
                  }}>+{c.size - 4}</div>
                </div>
                <div className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>Month {c.month}/{c.size}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============ Create circle ============
function CreateCircle({ onBack, onDone }) {
  const [amount, setAmount] = React.useState(500);
  const [freq, setFreq] = React.useState('monthly');
  const [size, setSize] = React.useState(10);
  const [name, setName] = React.useState('Brum Builders');

  return (
    <div className="screen no-tab">
      <NavHeader title="Create a circle" onBack={onBack} />
      <div className="section" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div className="field">
          <label>Circle name</label>
          <input className="input" value={name} onChange={e => setName(e.target.value)} />
        </div>

        <div className="field">
          <label>Contribution amount</label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
            {[50, 100, 500, 800].map(a => (
              <button key={a} onClick={() => setAmount(a)} className="option-tile" style={{
                padding: '14px 10px', justifyContent: 'center', flexDirection: 'column', gap: 2,
                background: amount === a ? 'var(--brand-soft)' : 'var(--surface)',
                borderColor: amount === a ? 'var(--brand)' : 'var(--line)',
              }}>
                <div className="mono" style={{ fontSize: 16, fontWeight: 600, color: amount === a ? 'var(--brand)' : 'var(--ink)' }}>£{a}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label>Frequency</label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {['weekly', 'monthly'].map(f => (
              <button key={f} onClick={() => setFreq(f)} className="option-tile" style={{
                padding: 14, justifyContent: 'center',
                background: freq === f ? 'var(--brand-soft)' : 'var(--surface)',
                borderColor: freq === f ? 'var(--brand)' : 'var(--line)',
              }}>
                <span style={{ fontSize: 14, fontWeight: 500, textTransform: 'capitalize' }}>{f}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label>Number of members <span className="mono" style={{ float: 'right', color: 'var(--ink)', fontWeight: 500 }}>{size}</span></label>
          <input type="range" min="5" max="10" value={size} onChange={e => setSize(+e.target.value)}
            style={{ width: '100%', accentColor: 'var(--brand)' }} />
          <div className="row-between" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
            <span>5</span><span>10</span>
          </div>
        </div>

        <div className="card" style={{ background: 'var(--surface-2)', border: 0, padding: 16 }}>
          <div className="label-xs" style={{ marginBottom: 8 }}>Summary</div>
          <div className="row-between" style={{ padding: '4px 0' }}>
            <span style={{ fontSize: 13.5, color: 'var(--ink-2)' }}>Each {freq}, everyone pays</span>
            <span className="mono" style={{ fontWeight: 500 }}>£{amount}</span>
          </div>
          <div className="row-between" style={{ padding: '4px 0' }}>
            <span style={{ fontSize: 13.5, color: 'var(--ink-2)' }}>One person receives</span>
            <span className="mono" style={{ fontWeight: 600, color: 'var(--brand)' }}>£{(amount * size).toLocaleString()}</span>
          </div>
          <div className="row-between" style={{ padding: '4px 0' }}>
            <span style={{ fontSize: 13.5, color: 'var(--ink-2)' }}>Cycle length</span>
            <span className="mono" style={{ fontWeight: 500 }}>{size} {freq === 'weekly' ? 'weeks' : 'months'}</span>
          </div>
        </div>

        <button className="btn btn-primary btn-xl btn-block" onClick={onDone}>
          Invite members
          <Icon.arrowR style={{ width: 18, height: 18 }} />
        </button>
      </div>
    </div>
  );
}

// ============ Member profile (username-only) ============
function MemberProfile({ onBack }) {
  const m = CIRCLE_MEMBERS.find(x => x.u === 'abel_o');
  return (
    <div className="screen no-tab">
      <NavHeader title="Member" onBack={onBack} />
      <div className="section" style={{ marginTop: 10 }}>
        <div className="card" style={{ textAlign: 'center', padding: '24px 20px' }}>
          <Avatar name={m.n} size="xl" style={{ margin: '0 auto 14px' }} />
          <div style={{ fontSize: 20, fontWeight: 600 }}>@{m.u}</div>
          <div style={{ fontSize: 13, color: 'var(--ink-3)', marginTop: 4 }}>Member since Jan 2025</div>
          <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginTop: 14, flexWrap: 'wrap' }}>
            <div className="pill good"><Icon.shield style={{ width: 12, height: 12 }}/> KYC verified</div>
            <div className="pill gold">Next payout</div>
            <div className="pill">2 circles</div>
          </div>
        </div>
      </div>

      <div className="section" style={{ marginTop: 14 }}>
        <div className="card-flat" style={{ display: 'flex', gap: 10, padding: 14, alignItems: 'flex-start' }}>
          <Icon.eyeOff style={{ width: 18, height: 18, color: 'var(--ink-3)', flexShrink: 0, marginTop: 2 }} />
          <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>
            Bank account details are never visible to you. Payouts route through AjoCredit's virtual accounts.
          </div>
        </div>
      </div>

      <div className="section" style={{ marginTop: 14 }}>
        <div className="h3" style={{ padding: '0 4px', marginBottom: 10 }}>Reliability</div>
        <div className="card" style={{ padding: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, textAlign: 'center' }}>
            {[
              ['14', 'circles'], ['100%', 'on-time'], ['0', 'defaults'],
            ].map(([v, l]) => (
              <div key={l}>
                <div className="mono" style={{ fontSize: 22, fontWeight: 600, color: 'var(--ink)' }}>{v}</div>
                <div style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 2 }}>{l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="section" style={{ marginTop: 14 }}>
        <div className="h3" style={{ padding: '0 4px', marginBottom: 10 }}>Credit standing</div>
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 13.5 }}>UK score band</div>
              <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 2 }}>Shown as band · exact score private</div>
            </div>
            <div className="pill good">Excellent</div>
          </div>
          <div style={{ height: 1, background: 'var(--line-2)' }} />
          <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 13.5 }}>Origin check</div>
              <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 2 }}>Nigeria · no pending debt</div>
            </div>
            <Icon.check style={{ width: 18, height: 18, color: 'var(--good)' }} />
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { CircleDetail, CircleOverview, MembersList, RotationView, Browse, CreateCircle, MemberProfile });
