# Credit bureaus

Research date: 21 October 2026. The UK bureaus in scope are Experian, Equifax, and TransUnion. Ajo may look a member up when deciding a contribution band, and may later report a completed circle cycle. Lookup and reporting are different contracts. Neither one posts ledger cash.

No public page read for this research offered a self-serve sandbox with test keys. Access is commercial: an account manager, a test file, and a signed agreement. Live reporting is blocked by [#66](https://github.com/abelunbound/ajocredit/issues/66). Real consumer data is also blocked by the data protection impact assessment, [#65](https://github.com/abelunbound/ajocredit/issues/65). Until those close, [#56](https://github.com/abelunbound/ajocredit/issues/56) is dummy reporting of completed UK cycles, and [#144](https://github.com/abelunbound/ajocredit/issues/144) keeps sample data off the live credit page.

## What each bureau offers

The three firms are separate. A lender can report to one, two, or all three. TransUnion's consumer guide says Experian's sharing database is CAIS and Equifax's is Insight, and that the three do not hold the same records. Source: [Your credit file explained (TransUnion PDF)](https://www.transunion.co.uk/content/dam/transunion/gb/consumer/collateral/your-credit-file-explained-v-9/Your%20credit%20file%20explained%20v9.pdf).

### Experian

[CAIS](https://www.experian.co.uk/cais/faqs) is Experian's shared database of consumer credit performance. Members who give consumer credit share performance data and, in return, can see CAIS data at the same level they contribute. The FAQ says membership is for firms that give consumer credit or lend to consumers, and lists conditions the FAQ itself still words as a consumer credit licence, Data Protection Act registration, a facility longer than the short trade-credit cases it excludes, customer consent to search and supply, and a complete accurate file every month. Full membership and default-only sharing are described in that FAQ. Joining starts with an Experian account manager, a test file, a signed CAIS agreement, and a source code. The first load is due within three months of signing, and updates are monthly.

The FAQ's phrase "consumer credit licence" is older than the FCA permission regime. Whether FCA authorisation is what Experian now asks to see is an open question for the account manager and for the adviser on [#59](https://github.com/abelunbound/ajocredit/issues/59). This research does not treat the FAQ wording as the current legal test.

[Rental Exchange](https://www.experian.co.uk/business/customer-insights/risk-analysis/rental-exchange/landlords-agents) puts a tenant's rent payment history on an Experian credit report. Experian's page says there is no cost to the agent, landlord, or tenant, and that Experian is the only UK credit reference agency that currently turns rental payment data into consumer credit reports. Landlords or agents with 500 or more properties are pointed at a contact form. Smaller ones are pointed at services that work with the Rental Exchange. That "only agency" sentence conflicts with the Equifax and TransUnion pages below, which describe rental data on their own files. Which file a rent payment actually appears on has to be confirmed with each bureau. It is an open question.

Ajo is not a landlord, and a circle contribution is not rent. Do not report circle contributions through Rental Exchange. Doing so would describe the wrong kind of payment.

### Equifax

[Insight](https://developer.equifax.co.uk/sites/uk/files/xml_ref_guide/ref/Data%20Groups/Insight.pdf) is Equifax's information-sharing database of credit agreements supplied by members. The reference says access follows the Principles of Reciprocity. Full members supply all accounts, positive and negative, and can see that level from other members. Partial members supply serious delinquency and see that level. Records are kept for six years from default or from settlement. The same PDF says further information comes from an Equifax account manager. The public XML reference describes fields a member request can return, including payment history. It is not a signup flow.

Equifax's consumer help says rental data on their file comes from CreditLadder, Bud, Inchora, Fea Card/Bits, and Canopy. Tenants report to those firms, and those firms supply Equifax. Source: [What is rental data and where does it come from?](https://help.equifax.co.uk/EquifaxOnlineHelp/s/article/What-is-rental-data-and-where-does-it-come-from). That list is not a general API for a savings circle to post contribution history.

### TransUnion

[SHARE](https://www.transunion.co.uk/content/dam/transunion/gb/consumer/collateral/your-credit-file-explained-v-9/Your%20credit%20file%20explained%20v9.pdf) is TransUnion's database of financial account information, supplied monthly by banks, building societies, finance houses, retailers, and also by utilities and other firms. The guide says SHARE can include rent payment history when the person or their landlord has signed up to share it. In general, organisations that contribute can access SHARE, under rules the guide says every member must follow. A financial agreement that is missing from a file is often missing because that firm does not contribute, or contributes to a different bureau.

TransUnion's credit reference notice also lists rental data (tenancy reference, dates, rent, arrangement, balance) from social landlords, private landlords, and services that read rent from a bank account, plus current-account turnover and open-banking data obtained where an FCA-registered account information service is allowed to supply it. Source: [Credit Reference Agency Information Notice](https://www.transunion.co.uk/legal/privacy-centre/pc-credit-reference).

## What is useful for Ajo

Two uses, kept separate:

1. **Lookup, as an input to affordability.** A search of CAIS, Insight, or SHARE can show credit commitments the bank feed does not label. [#52](https://github.com/abelunbound/ajocredit/issues/52) stores a band and reasons, not the raw report. The lookup is specified in [affordability.md](affordability.md). Reciprocity may mean a firm that wants to see full performance data is expected to supply data at that level. Confirm that with the bureau before relying on a lookup-only contract.
2. **Reporting a completed cycle ([#56](https://github.com/abelunbound/ajocredit/issues/56)).** After a circle's Modulr balance matches the ledger, a monthly dummy file can be built in the shape the chosen bureau specifies. Live submission waits for [#66](https://github.com/abelunbound/ajocredit/issues/66). The member can see the row we would send and can dispute it (SR-33).

Whether a rotating-savings contribution is a credit agreement CAIS, Insight, or SHARE will accept is an open question. Experian's CAIS FAQ limits membership to firms that give consumer credit, with the exceptions it lists for TV rental and utilities. A savings circle may fall outside that. Delay Cover, if an adviser decides it is credit, is a clearer candidate for a performance record than the ordinary contribution. [#59](https://github.com/abelunbound/ajocredit/issues/59) has to be answered before a live file calls anyone a borrower.

Report UK members only, as [#56](https://github.com/abelunbound/ajocredit/issues/56) says. The product's Nigeria path is locked in the current UI and is out of scope for these bureaus.

## End to end

Lookup, when a bureau contract exists:

1. The member has consented. Consent text is part of [#65](https://github.com/abelunbound/ajocredit/issues/65) and of the bureau's own wording. The audit name `consent_given` is already listed.
2. The server sends a search for that member to the bureau using the credentials in the secrets store. The search type (quotation search or application search, and whether it leaves a footprint) was not fixed by the pages read. Confirm it with the bureau. A footprint the member did not expect is a harm to avoid.
3. The response is reduced to the figures the affordability rules need (existing committed payments, and any reason code we are allowed to keep). The full response is not stored and not logged.
4. The band, maximum contribution, and reasons are stored as in [affordability.md](affordability.md). The bureau's search reference can be kept so a dispute can be traced. The raw XML or JSON is not a ledger entry and not an audit payload.

Reporting, dummy until [#66](https://github.com/abelunbound/ajocredit/issues/66):

1. A cycle is eligible when every scheduled contribution and payout for that cycle has a ledger entry, each money movement's `reference` matches a confirmed Modulr payment, and the reconciliation in [modulr.md](modulr.md) is clear. SR-33 forbids reporting a cycle that has not been reconciled.
2. Build one row per member for that cycle from the ledger: amount due, amount paid, whether the month was on time, and any reserve receivable still open. Use synthetic identities in every file until the gate closes.
3. Show that row to the member before a live send. A dispute holds the row out of the file and writes an audit event. There is no listed audit name for a bureau dispute yet. Adding one is part of [#56](https://github.com/abelunbound/ajocredit/issues/56), not this docs change.
4. Submit on the bureau's monthly timetable once [#66](https://github.com/abelunbound/ajocredit/issues/66) is signed. Experian's FAQ says CAIS updates are monthly and should be taken at the same point in the month. Equifax and TransUnion also describe monthly supply. The file format is the one in the bureau's member pack. Experian publishes a CAIS file specification to members via the account manager. This research does not copy that specification into the repo.
5. A correction after submission is a new submission the bureau accepts, and a reversing ledger entry if the money was wrong. The original ledger row stays.

[#144](https://github.com/abelunbound/ajocredit/issues/144) removes sample bureau data from the credit page, stores live credentials in the secrets manager, and shows real bureau data only for a consenting test user.

## Ledger and members

No bureau event changes `asset:partner` or a member liability. The ledger is the source the file is built from, after reconciliation.

Figures a reporting row may take from the ledger, using synthetic refs in dummy files:

| Figure | Ledger source |
|---|---|
| Contribution due and paid | Credits on `liability:{member_ref}:{circle_ref}` whose descriptions are contributions, matched to Modulr `PaymentId` references |
| Payout received | The payout entry that debits that liability and credits the circle asset |
| Still owed to the reserve | Balance of `asset:receivable:{member_ref}:{circle_ref}`, once [#63](https://github.com/abelunbound/ajocredit/issues/63) opens that account |
| On time or late | Audit events `contribution_paid`, `contribution_late`, `contribution_missed`, compared with the circle calendar |

A reserve top-up must not be reported as a contribution the member paid. The receivable, if the adviser agrees it is credit, is the candidate record. Ordinary pot payments are candidate records only if the bureau and the adviser both agree they are reportable. Until then the dummy file should label each row `synthetic-not-for-submission` and stay inside the git-ignored local data or a test fixture that uses `@example.test` identities.

The member sees their own row. They do not see another member's bureau data. Circle admins do not receive a bureau extract. A platform admin view is `financial_data_viewed`.

Reconciliation of reporting is a count: every reconciled UK cycle in the month is either in the dummy file, held for dispute, or listed with a reason. The file total of pence paid equals the ledger credits for those contributions. A mismatch stops submission.

## Sandbox and test steps

Public signup steps were not found.

| Bureau | What the public docs say to do | What was not found |
|---|---|---|
| Experian CAIS | Contact an account manager. Compile a test file. Sign the agreement. Receive a source code. Load within three months | A public sandbox URL or a test API key |
| Equifax Insight | The XML reference says to ask an Equifax account manager. Developer reference material is published under [developer.equifax.co.uk](https://developer.equifax.co.uk/sites/uk/files/xml_ref_guide/ref/Data%20Groups/Insight.pdf) | A self-serve sandbox signup on the pages read |
| TransUnion SHARE | The consumer guide describes monthly supply by member firms | A public developer sandbox URL |

Until an account manager issues a test environment:

1. Build the dummy monthly file from the synthetic ledger seed (`circle-synth-ci-balance`, `member-ada`, `member-bo`) or from `@example.test` personas.
2. Check the file against the column list in this document, not against a guessed bureau layout.
3. Do not POST it anywhere.
4. When a bureau issues test credentials, store them as below and run one synthetic file in their test environment. Record the acceptance or rejection reason in the ticket, not in git.

[#66](https://github.com/abelunbound/ajocredit/issues/66) is the gate that replaces this dummy with a signed live feed.

## Keys and config

Not added to `.env.example` in this change. Names are proposals for whichever bureau [#66](https://github.com/abelunbound/ajocredit/issues/66) signs. Do not invent a second bureau's keys "just in case" in the secrets store.

| Name | Where | Notes |
|---|---|---|
| `BUREAU_PROVIDER` | config | `experian`, `equifax`, or `transunion`, once one is chosen |
| `BUREAU_CLIENT_ID` | `.env`, GitHub Actions secret, or the production secrets manager | Placeholder name. The bureau's own field name may differ |
| `BUREAU_CLIENT_SECRET` | same | Never committed |
| `BUREAU_BASE_URL` | config | Test or live URL from the member pack, not from this document |
| `BUREAU_SOURCE_CODE` | secret or config | Experian's FAQ describes a source code that identifies the portfolio. The other bureaus may use a different id |

CI must not call a bureau. [#145](https://github.com/abelunbound/ajocredit/issues/145) keeps live keys in the production secrets manager.

## Risks and open questions

- Reporting a savings contribution as rent, or as a loan, would put a false account on a credit file. That is the harm in threat T-29. SR-33 limits reporting to reconciled cycles and requires a member-visible dispute path. The legal character of the product is [#59](https://github.com/abelunbound/ajocredit/issues/59).
- CAIS membership, as the FAQ describes it, expects a consumer-credit lender's permission and monthly files. Ajo may be ineligible until [#59](https://github.com/abelunbound/ajocredit/issues/59) is decided. Insight and SHARE have their own membership rules. This research did not read an Equifax or TransUnion membership contract.
- Principles of Reciprocity, named on the Equifax Insight page, tie what we can see to what we supply. A lookup without reporting may be unavailable or partial.
- A credit search can leave a footprint. The search type is unconfirmed.
- Experian's "only agency" rental claim and the Equifax and TransUnion rental pages disagree. Do not rely on the marketing sentence.
- Six-year retention, stated for Insight records, may conflict with a shorter retention we want under [#65](https://github.com/abelunbound/ajocredit/issues/65). The adviser and the bureau have to agree what a deletion request can actually remove from a bureau file.
- Dummy files must stay synthetic. A real name, a real address, or a real account number in a test file is a report about a real person.
- There is no code yet that talks to a bureau. The credit page still shows sample figures. [#144](https://github.com/abelunbound/ajocredit/issues/144) removes those from the live path.

## Tickets

| Ticket | How this document maps |
|---|---|
| [#56](https://github.com/abelunbound/ajocredit/issues/56) | Monthly dummy reporting of completed UK cycles, after reconciliation |
| [#52](https://github.com/abelunbound/ajocredit/issues/52) | Lookup as an input to the band. See [affordability.md](affordability.md) |
| [#66](https://github.com/abelunbound/ajocredit/issues/66) | Signed bureau agreement before any live report |
| [#65](https://github.com/abelunbound/ajocredit/issues/65) | DPIA before real bureau data |
| [#59](https://github.com/abelunbound/ajocredit/issues/59) | Whether the product is credit, which decides if CAIS-style reporting is even eligible |
| [#144](https://github.com/abelunbound/ajocredit/issues/144) | Remove sample bureau data and use live credentials for one consenting test user |
| [#63](https://github.com/abelunbound/ajocredit/issues/63) | The receivable is the candidate reportable balance, if an adviser agrees |

## Sources

- [Experian CAIS FAQ](https://www.experian.co.uk/cais/faqs)
- [Experian, joining CAIS](https://www.experian.co.uk/blogs/latest-thinking/data-quality/experian-cais-join-the-experian-bureau-with-seamless-and-swift-onboarding/)
- [Experian Rental Exchange for landlords and agents](https://www.experian.co.uk/business/customer-insights/risk-analysis/rental-exchange/landlords-agents)
- [Equifax Insight data group (XML reference PDF)](https://developer.equifax.co.uk/sites/uk/files/xml_ref_guide/ref/Data%20Groups/Insight.pdf)
- [Equifax: what rental data is and where it comes from](https://help.equifax.co.uk/EquifaxOnlineHelp/s/article/What-is-rental-data-and-where-does-it-come-from)
- [TransUnion: Your credit file explained (PDF)](https://www.transunion.co.uk/content/dam/transunion/gb/consumer/collateral/your-credit-file-explained-v-9/Your%20credit%20file%20explained%20v9.pdf)
- [TransUnion Credit Reference Agency Information Notice](https://www.transunion.co.uk/legal/privacy-centre/pc-credit-reference)
