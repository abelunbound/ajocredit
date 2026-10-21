# Partners

Research date: 21 October 2026. Pages on the public web change. Where a fact was not on the page, it is an open question. This folder is research for later tickets. It does not open accounts, post ledger rows, or add configuration.

Ajo is a UK rotating savings circle. Members contribute, and one member receives that month's payout. Later milestones add Delay Cover (a reserve tops up a late contribution), Early Payout (a member takes cash already paid in, ahead of their turn), and a report of completed cycles to a UK credit bureau. The ledger in [docs/ledger.md](../ledger.md) is the append-only record of that money, in integer pence. Partner responses are checked before a row is posted. The threat model in [docs/security/THREAT_MODEL.md](../security/THREAT_MODEL.md) is the source for the controls named below.

## Summary

| Document | Partner | What Ajo uses it for | Moves circle money? | Writes the ledger? |
|---|---|---|---|---|
| [modulr.md](modulr.md) | Modulr FS, an FCA-authorised e-money institution | Accounts, pay-ins, direct debit collections, payouts, webhooks | Yes | Yes, after the payment is confirmed |
| [truelayer.md](truelayer.md) | TrueLayer | Read-only bank data, account-holder name match, affordability inputs | No | No cash entry |
| [credit-bureau.md](credit-bureau.md) | Experian, Equifax, TransUnion | Lookup at decision time, and later reporting of completed cycles | No | No cash entry |
| [affordability.md](affordability.md) | Our rules, fed by TrueLayer and a bureau | Band, maximum contribution, and reasons. A person reviews a decline | No | No cash entry |

## How they fit together

One member, one circle, in the order the milestones build it.

1. The member signs up and verifies their email. Identity verification is a separate dummy flow ([#50](https://github.com/abelunbound/ajocredit/issues/50)).
2. The member connects a UK bank through TrueLayer and consents to the least data the check needs ([#43](https://github.com/abelunbound/ajocredit/issues/43)). The account-holder name is compared with the verified identity. Tokens stay encrypted. Raw transactions are not stored.
3. The affordability rules turn that summary, and a bureau lookup where one is needed, into a band, a maximum contribution in pence, and reasons ([#52](https://github.com/abelunbound/ajocredit/issues/52)). A decline waits for a person. The result is a band, not a pass or fail.
4. The member joins a circle. The contribution they choose cannot sit above the stored maximum.
5. Creating the circle opens a Modulr GBP account for that circle, and the ledger account `asset:partner:{circle_ref}` that already exists in the chart. The member's position is `liability:{member_ref}:{circle_ref}`.
6. Each month the member pays by direct debit or bank transfer ([#51](https://github.com/abelunbound/ajocredit/issues/51)). A signed Modulr webhook is reconciled to Modulr's own payment record. Only then does the ledger debit the circle asset and credit the member liability.
7. The scheduled recipient is paid from that circle account ([#54](https://github.com/abelunbound/ajocredit/issues/54)). The ledger debits their liability and credits the circle asset. The payout reference is the Modulr payment id, so a second delivery of the same event cannot post twice.
8. If a contribution is late, the reserve account tops up the circle ([#63](https://github.com/abelunbound/ajocredit/issues/63)). That reserve is a separate Modulr account from the circle accounts. The late member owes it back through the next cycle or a direct debit retry ([#60](https://github.com/abelunbound/ajocredit/issues/60)).
9. An early payout quote is computed on the server and is not a ledger entry ([#64](https://github.com/abelunbound/ajocredit/issues/64)). On accept, the ledger pays at most the amount that member has already paid in ([#57](https://github.com/abelunbound/ajocredit/issues/57), [#61](https://github.com/abelunbound/ajocredit/issues/61)). The pilot fee is £0 ([#59](https://github.com/abelunbound/ajocredit/issues/59)).
10. When the cycle is finished and the circle's Modulr balance matches the ledger, the reporting file for that cycle can be prepared ([#56](https://github.com/abelunbound/ajocredit/issues/56)). The member can see what would be reported. Nothing is sent to a live bureau until [#66](https://github.com/abelunbound/ajocredit/issues/66) is signed.
11. Alpha ([#141](https://github.com/abelunbound/ajocredit/issues/141)) switches each sandbox to the live service only after the gates below are closed: Modulr ([#142](https://github.com/abelunbound/ajocredit/issues/142)), TrueLayer ([#143](https://github.com/abelunbound/ajocredit/issues/143)), the bureau ([#144](https://github.com/abelunbound/ajocredit/issues/144)), and production secrets ([#145](https://github.com/abelunbound/ajocredit/issues/145)). The first live circle is [#146](https://github.com/abelunbound/ajocredit/issues/146).

TrueLayer and the bureaus describe the member. Modulr holds and moves the money. The ledger is the book that must still balance if a partner message is repeated, delayed, or reversed.

## Gates a person has to close

These gates do not block dummy builds. They block live use.

| Gate | What it blocks |
|---|---|
| [#59](https://github.com/abelunbound/ajocredit/issues/59) Legal check of the fee-free credit exemption | Real-member Delay Cover and Early Payout. Fees stay £0 until a licence or a lender is in place |
| [#62](https://github.com/abelunbound/ajocredit/issues/62) Modulr sandbox access | Real money movement in M4 to M6. Until then, build against mocks |
| [#65](https://github.com/abelunbound/ajocredit/issues/65) Data protection impact assessment | Any real user. Covers Open Banking, bureau, identity, and ethnicity data |
| [#66](https://github.com/abelunbound/ajocredit/issues/66) Credit bureau signed | Live reporting under M7 |

Safeguarding, client money, and whether a circle contribution or a reserve top-up is consumer credit are questions for a human adviser. They are written out in [modulr.md](modulr.md) and [affordability.md](affordability.md). This research does not answer them.

## Secrets

Keys live in a developer's untracked `.env`, in GitHub Actions secrets when a job is explicitly allowed to call a sandbox, and in the production secrets manager ([#145](https://github.com/abelunbound/ajocredit/issues/145)). They are not committed. `.env.example` has no partner variables yet, and this change does not add code or config. The names to use when those tickets are built are listed in each partner document. Placeholders only.
