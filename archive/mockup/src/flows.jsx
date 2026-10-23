// ===== Payout, Auto-loan, Wallet, Profile =====

function PayoutFlow({ onBack, onDone }) {
  const [stage, setStage] = React.useState('select'); // select | review | success

  if (stage === 'success') {
    return (
      <div className="screen no-tab" style={{ display: 'flex', flexDirection: 'column' }}>
        <NavHeader title="Payout sent" onBack={onDone} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 24px', textAlign: 'center' }}>
          <div style={{
            width: 80, height: 80, borderRadius: '50%',
            background: 'var(--good-soft)', color: 'var(--good)',
            display: 'grid', placeItems: 'center', marginBottom: 20,
          }}>
            <Icon.check style={{ width: 40, height: 40, strokeWidth: 3 }} />
          </div>
          <div className="h2" style={{ marginBottom: 8 }}>£5,000 credited</div>
          <div style={{ color: 'var(--ink-3)', fontSize: 14, marginBottom: 28 }}>
            Abel O.'s virtual account received the full pot.
          </div>
          <div className="card" style={{ width: '100%', maxWidth: 320, padding: 16, textAlign: 'left' }}>
            <div className="row-between" style={{ padding: '6px 0' }}>
              <span style={{ fontSize: 13, color: 'var(--ink-3)' }}>Recipient</span>
              <span style={{ fontSize: 13, fontWeight: 500 }}>@abel_o</span>
            </div>
            <div className="row-between" style={{ padding: '6px 0' }}>
              <span style={{ fontSize: 13, color: 'var(--ink-3)' }}>Method</span>
              <span style={{ fontSize: 13, fontWeight: 500 }}>Virtual account</span>
            </div>
            <div className="row-between" style={{ padding: '6px 0' }}>
              <span style={{ fontSize: 13, color: 'var(--ink-3)' }}>Reference</span>
              <span className="mono" style={{ fontSize: 12 }}>AJO-BBM-03-0428</span>
            </div>
          </div>
        </div>
        <div className="section">
          <button className="btn btn-primary btn-xl btn-block" onClick={onDone}>Done</button>
        </div>
      </div>
    );
  }

  if (stage === 'review') {
    return (
      <div className="screen no-tab">
        <NavHeader title="Review payout" onBack={() => setStage('select')} />
        <div className="section">
          <div className="card" style={{ padding: 20, textAlign: 'center' }}>
            <div className="label-xs">Releasing to</div>
            <Avatar name="Abel O." size="xl" style={{ margin: '12px auto 10px' }} />
            <div style={{ fontSize: 16, fontWeight: 600 }}>@abel_o</div>
            <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 2 }}>Abel O. · Month 3 recipient</div>
            <div className="mono" style={{ fontSize: 40, fontWeight: 600, letterSpacing: '-0.03em', marginTop: 18 }}>£5,000</div>
          </div>
        </div>

        <div className="section" style={{ marginTop: 14 }}>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {[
              ['Method', <span className="row-center" style={{ gap: 6 }}><Icon.wallet style={{ width: 14, height: 14 }}/> Virtual account</span>],
              ['Settlement', 'Instant · Faster Payments'],
              ['Contributions collected', '9 of 10 · £4,500'],
              ['Auto-loan covers', 'Daniel K. · £500 · 0% APR'],
              ['Fee', 'Free · included in monthly'],
            ].map(([k, v], i, a) => (
              <div key={k} style={{
                padding: '12px 14px',
                borderBottom: i < a.length - 1 ? '1px solid var(--line-2)' : 'none',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div style={{ fontSize: 13, color: 'var(--ink-3)' }}>{k}</div>
                <div style={{ fontSize: 13.5, fontWeight: 500 }}>{v}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="section" style={{ marginTop: 14 }}>
          <div className="card-flat" style={{ display: 'flex', gap: 10, padding: 14, alignItems: 'flex-start' }}>
            <Icon.lock style={{ width: 18, height: 18, color: 'var(--ink-3)', flexShrink: 0, marginTop: 2 }} />
            <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>
              Abel's bank details are hidden. Funds move via AjoCredit's virtual account and land in his linked bank automatically.
            </div>
          </div>
        </div>

        <div style={{ padding: '20px 20px 0' }}>
          <button className="btn btn-primary btn-xl btn-block" onClick={() => setStage('success')}>
            <Icon.lock style={{ width: 16, height: 16 }} /> Hold to release £5,000
          </button>
          <button className="btn btn-ghost btn-block" style={{ marginTop: 8 }} onClick={() => setStage('select')}>
            Back
          </button>
        </div>
      </div>
    );
  }

  // select
  return (
    <div className="screen no-tab">
      <NavHeader title="Release payout" onBack={onBack} />
      <div className="section">
        <div className="label-xs">Month 3 of 10</div>
        <div className="h2" style={{ margin: '6px 0 4px' }}>Who receives this month?</div>
        <div className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
          Rotation says <strong style={{ color: 'var(--ink)' }}>Abel O.</strong> Admins can swap only with member consent.
        </div>
      </div>
      <div className="section">
        <div style={{ display: 'grid', gap: 8 }}>
          {CIRCLE_MEMBERS.filter(m => !m.done).slice(0, 6).map(m => (
            <button key={m.u} onClick={() => setStage('review')}
              className={`option-tile ${m.next ? 'selected' : ''}`}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flex: 1 }}>
                <Avatar name={m.n} />
                <div style={{ textAlign: 'left', flex: 1 }}>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span style={{ fontWeight: 500, fontSize: 14.5 }}>@{m.u}</span>
                    {m.next && <span className="pill gold" style={{ height: 18, fontSize: 10, padding: '0 6px' }}>scheduled</span>}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 2 }}>Position #{m.position} · score {m.score}</div>
                </div>
                <div className="option-check"><Icon.check /></div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============ Auto-loan ============
function AutoLoan({ onBack }) {
  const [on, setOn] = React.useState(true);
  return (
    <div className="screen no-tab">
      <NavHeader title="Auto-loan" onBack={onBack} />
      <div className="section">
        <div className="card" style={{
          padding: 20, color: '#fff',
          background: 'linear-gradient(135deg, #B88A2A, #8A6420)',
          border: 0, position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ position: 'absolute', right: -30, top: -30, width: 160, height: 160, borderRadius: '50%', background: 'rgba(255,255,255,0.08)' }} />
          <div className="row-center" style={{ marginBottom: 14, position: 'relative' }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(255,255,255,0.18)', display: 'grid', placeItems: 'center' }}>
              <Icon.bolt style={{ width: 18, height: 18 }} />
            </div>
            <div style={{ fontWeight: 600, fontSize: 15 }}>Interest-free safety net</div>
          </div>
          <div className="h2" style={{ position: 'relative' }}>
            Payouts go out on time — <span className="serif">even when someone's late.</span>
          </div>
          <div style={{ fontSize: 13, opacity: 0.9, marginTop: 10, position: 'relative', lineHeight: 1.5 }}>
            If a member misses their contribution, AjoCredit covers it as a 0% loan so the recipient still gets the full pot on schedule.
          </div>
        </div>
      </div>

      <div className="section" style={{ marginTop: 14 }}>
        <div className="card" style={{ padding: 16 }}>
          <div className="row-between">
            <div>
              <div style={{ fontWeight: 500, fontSize: 15 }}>Auto-loan for this circle</div>
              <div style={{ fontSize: 12.5, color: 'var(--ink-3)', marginTop: 3 }}>Brum Builders · 10 members</div>
            </div>
            <button onClick={() => setOn(!on)} style={{
              width: 46, height: 28, borderRadius: 20,
              background: on ? 'var(--brand)' : 'var(--line)',
              padding: 3, transition: 'background .2s',
            }}>
              <div style={{
                width: 22, height: 22, borderRadius: '50%', background: '#fff',
                transform: on ? 'translateX(18px)' : 'translateX(0)',
                transition: 'transform .2s', boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
              }} />
            </button>
          </div>
          <div style={{ height: 1, background: 'var(--line-2)', margin: '14px 0' }} />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Coverage</div>
              <div className="mono" style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>Up to £500</div>
              <div style={{ fontSize: 11.5, color: 'var(--ink-3)' }}>1 missed contribution</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Your APR</div>
              <div className="mono" style={{ fontSize: 18, fontWeight: 600, marginTop: 2, color: 'var(--good)' }}>0.0%</div>
              <div style={{ fontSize: 11.5, color: 'var(--ink-3)' }}>Repay over 60 days</div>
            </div>
          </div>
        </div>
      </div>

      <div className="section" style={{ marginTop: 14 }}>
        <div className="h3" style={{ padding: '0 4px', marginBottom: 10 }}>How it works</div>
        <div style={{ display: 'grid', gap: 10 }}>
          {[
            ['Someone misses a contribution', 'Grace period gives them 48 hours to catch up.'],
            ['AjoCredit steps in', 'We front the missing amount — 0% interest, no fees.'],
            ['Recipient gets the full pot', 'On the scheduled date. No delay. No drama.'],
            ['Late member repays', 'Automatic debit over 60 days from their next contributions.'],
          ].map(([t, s], i) => (
            <div key={i} className="card" style={{ padding: 14, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <div className="mono" style={{
                width: 28, height: 28, borderRadius: 8,
                background: 'var(--brand-soft)', color: 'var(--brand)',
                display: 'grid', placeItems: 'center',
                fontSize: 13, fontWeight: 600, flexShrink: 0,
              }}>{i + 1}</div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{t}</div>
                <div style={{ fontSize: 12.5, color: 'var(--ink-3)', marginTop: 3, lineHeight: 1.5 }}>{s}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="section" style={{ marginTop: 14 }}>
        <div className="card-flat" style={{ padding: 14 }}>
          <div className="row-between">
            <div style={{ fontSize: 13, color: 'var(--ink-2)' }}>Coverage used this cycle</div>
            <div className="mono" style={{ fontSize: 13, fontWeight: 500 }}>£0 / £500</div>
          </div>
          <div className="bar" style={{ marginTop: 8 }}><span style={{ width: '0%' }} /></div>
        </div>
      </div>
    </div>
  );
}

// ============ Wallet ============
function Wallet({ onNav }) {
  return (
    <>
      <TopBar title="Wallet" />
      <div className="screen">
        <div className="section">
          <div className="card" style={{ padding: 20 }}>
            <div className="label-xs">Virtual account balance</div>
            <div className="mono" style={{ fontSize: 36, fontWeight: 600, letterSpacing: '-0.03em', marginTop: 4 }}>£42.18</div>
            <div style={{ fontSize: 12.5, color: 'var(--ink-3)', marginTop: 4 }}>
              Account · <span className="mono">AJO-230-5587-1144</span>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button className="btn btn-ghost btn-sm" style={{ flex: 1 }}><Icon.arrowDown style={{ width: 14, height: 14 }}/> Top up</button>
              <button className="btn btn-ghost btn-sm" style={{ flex: 1 }}><Icon.arrowUp style={{ width: 14, height: 14 }}/> Withdraw</button>
              <button className="btn btn-ghost btn-sm" style={{ flex: 1 }}><Icon.send style={{ width: 14, height: 14 }}/> Send</button>
            </div>
          </div>
        </div>

        <div className="section" style={{ marginTop: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div className="card" style={{ padding: 14 }}>
              <div className="label-xs">Lifetime in</div>
              <div className="mono" style={{ fontSize: 20, fontWeight: 600, marginTop: 4, color: 'var(--good)' }}>£10,510</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="label-xs">Lifetime out</div>
              <div className="mono" style={{ fontSize: 20, fontWeight: 600, marginTop: 4 }}>£10,000</div>
            </div>
          </div>
        </div>

        <div className="section" style={{ marginTop: 18 }}>
          <div className="h3" style={{ padding: '0 4px', marginBottom: 10 }}>All activity</div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {TXNS.map((t, i, a) => (
              <div key={t.id} className="row row-flat" style={{
                borderBottom: i < a.length - 1 ? '1px solid var(--line-2)' : 'none',
                borderRadius: 0,
                opacity: t.future ? 0.55 : 1,
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
                  <div className="sub">{t.date} · <span style={{ color: t.status === 'queued' ? 'var(--gold)' : 'var(--ink-3)' }}>{t.status}</span></div>
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

// ============ Circles list ============
function CirclesList({ onNav }) {
  return (
    <>
      <TopBar title="Circles" />
      <div className="screen">
        <div className="section">
          <div className="segment" style={{ marginBottom: 14 }}>
            <button className="on">Active · 1</button>
            <button>Past · 2</button>
            <button>Invites · 1</button>
          </div>
          <button onClick={() => onNav('circle-detail')} className="card" style={{
            width: '100%', textAlign: 'left', padding: 18, border: 0,
            background: 'linear-gradient(135deg, var(--brand), color-mix(in srgb, var(--brand) 80%, black))',
            color: 'var(--brand-ink)',
          }}>
            <div className="row-between" style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 16, fontWeight: 600 }}>{CIRCLE.name}</div>
              <div className="pill" style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', border: 0 }}>Month {CIRCLE.month}/{CIRCLE.size}</div>
            </div>
            <div className="mono" style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em', marginTop: 8 }}>
              £{CIRCLE.pot.toLocaleString()}
            </div>
            <div style={{ fontSize: 12.5, opacity: 0.85 }}>monthly pot · {CIRCLE.size} members</div>
            <div className="bar" style={{ marginTop: 14, background: 'rgba(255,255,255,0.2)' }}>
              <span style={{ width: '30%', background: '#fff' }} />
            </div>
          </button>
        </div>

        <div className="section" style={{ marginTop: 14 }}>
          <div className="h3" style={{ padding: '0 4px', marginBottom: 10 }}>Discover</div>
          <div style={{ display: 'grid', gap: 10 }}>
            {OTHER_CIRCLES.slice(0, 2).map((c, i) => (
              <button key={i} onClick={() => onNav('browse')} className="card" style={{ textAlign: 'left', padding: 14 }}>
                <div className="row-between" style={{ marginBottom: 4 }}>
                  <div style={{ fontWeight: 500, fontSize: 14.5 }}>{c.name}</div>
                  <Icon.chevR style={{ width: 16, height: 16, color: 'var(--ink-4)' }} />
                </div>
                <div style={{ fontSize: 12.5, color: 'var(--ink-3)' }}>
                  £{c.amount} {c.freq} · {c.size} members · {c.open ? 'Open' : 'Full'}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ============ Profile (self) ============
function Profile({ role, onRoleChange }) {
  return (
    <>
      <TopBar title="Profile" />
      <div className="screen">
        <div className="section">
          <div className="card" style={{ padding: 20, display: 'flex', gap: 14, alignItems: 'center' }}>
            <Avatar name={ME.name} size="xl" />
            <div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>@{ME.username}</div>
              <div style={{ fontSize: 13, color: 'var(--ink-3)', marginTop: 2 }}>{ME.city}</div>
              <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                <div className="pill good"><Icon.shield style={{ width: 12, height: 12 }}/> KYC</div>
                <div className="pill brand">Credit verified</div>
              </div>
            </div>
          </div>
        </div>

        <div className="section" style={{ marginTop: 14 }}>
          <div className="h3" style={{ padding: '0 4px', marginBottom: 10 }}>Viewing as</div>
          <div className="segment" style={{ width: '100%', display: 'flex' }}>
            <button className={role === 'member' ? 'on' : ''} onClick={() => onRoleChange('member')} style={{ flex: 1, padding: '10px 12px' }}>Member</button>
            <button className={role === 'admin' ? 'on' : ''} onClick={() => onRoleChange('admin')} style={{ flex: 1, padding: '10px 12px' }}>Admin</button>
          </div>
          <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 8, padding: '0 4px' }}>
            Demo toggle — admins can release payouts & manage members.
          </div>
        </div>

        <div className="section" style={{ marginTop: 14 }}>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {[
              ['Credit score', '791 · Good', Icon.chart],
              ['Identity (KYC)', 'Verified', Icon.shield],
              ['Linked bank', 'Monzo · ••3391', Icon.wallet],
              ['Notifications', 'On', Icon.bell],
              ['Privacy', 'Username-only mode', Icon.eyeOff],
              ['Help', '', Icon.book],
            ].map(([k, v, Ic], i, a) => (
              <div key={k} className="row row-flat" style={{
                padding: '14px 16px',
                borderBottom: i < a.length - 1 ? '1px solid var(--line-2)' : 'none',
                borderRadius: 0,
              }}>
                <div style={{ width: 32, height: 32, borderRadius: 9, background: 'var(--surface-2)', color: 'var(--ink-2)', display: 'grid', placeItems: 'center' }}>
                  <Ic style={{ width: 16, height: 16 }} />
                </div>
                <div className="main"><div style={{ fontSize: 14 }}>{k}</div></div>
                {v && <div style={{ fontSize: 12.5, color: 'var(--ink-3)' }}>{v}</div>}
                <Icon.chevR style={{ width: 14, height: 14, color: 'var(--ink-4)' }} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { PayoutFlow, AutoLoan, Wallet, CirclesList, Profile });
