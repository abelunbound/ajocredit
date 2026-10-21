# Affordability

Research date: 21 October 2026. This is Ajo's decision, not a fourth company. TrueLayer supplies a bank summary. A credit bureau may supply commitments. Our rules turn those into a band, a maximum contribution in pence, and reasons. The result is stored. The raw inputs are not.

The ticket is [#52](https://github.com/abelunbound/ajocredit/issues/52): a rules-based affordability band and maximum contribution. Store the band and the reasons, not raw transactions. A decline goes to a person. The result is not pass or fail.

The screen today (Financial Health Overview, `/credit`) shows fixed sample figures such as tuition and a bank balance. Those figures are not this check. [#144](https://github.com/abelunbound/ajocredit/issues/144) removes sample bureau data from the live credit page later. This document does not change that screen.

## What we use, and why

| Input | Source | Role in the band |
|---|---|---|
| Account-holder name | TrueLayer `info` / verification | Must match the verified identity or the check stops. This is identity, not affordability |
| Income and spending, read once | TrueLayer `accounts` and `transactions` | What is coming in, and what is already going out, over the window the rules name |
| Existing credit commitments | Experian CAIS, Equifax Insight, or TransUnion SHARE, if a contract allows a search | Payments the bank feed may not label as credit |
| The circle's contribution | The member's choice, in pence | Compared with the maximum the rules return |

Itemised TrueLayer and bureau facts, including sandbox limits and what their public docs do not promise, are in [truelayer.md](truelayer.md) and [credit-bureau.md](credit-bureau.md).

Ethnicity is never an input, even if the member answered the optional question. The threat model already requires a test that affordability code cannot read it (SR-08).

## FCA expectations, and what they do not settle

[CONC 5.2A](https://handbook.fca.org.uk/handbook/conc5/conc5s6) is the FCA's creditworthiness section for consumer credit lending, as read on 21 October 2026 (the handbook page says it was last updated on 4 November 2024). It requires a reasonable assessment before a firm enters a regulated credit agreement, significantly increases the credit, or significantly increases a running-account limit. The assessment covers credit risk (repayments not made when due) and affordability risk (the customer cannot repay in the way CONC 5.2A.12R describes). The firm has to consider the customer's ability to repay over the life of the agreement from income, from income it is reasonable to treat as available to them, or from savings they have clearly said they will use, without borrowing to make the repayments, without missing other contractual or statutory payments, and without a significant adverse effect on their financial situation. The information has to be sufficient, obtained from the customer where appropriate and from a credit reference agency where necessary.

The FCA does not prescribe Open Banking, a particular bureau, or a formula. The FCA's own note on [common misunderstandings](https://www.fca.org.uk/firms/creditworthiness-and-affordability-common-misunderstandings) says the obligation is to assess creditworthiness, of which the ability to repay is a part, and that the FCA does not prescribe the checks. Policies have to be effective. [PS18/19](https://www.fca.org.uk/publications/policy-statements/ps18-19-assessing-creditworthiness-consumer-credit) is the policy statement for those rules. Its opening chapter distinguishes credit risk from affordability and says a credit-information market study would look at new sources, including the possible impact of Open Banking. That sentence is not a rule that a firm must use Open Banking.

**Whether CONC 5.2A applies to Ajo is an open question for the adviser on [#59](https://github.com/abelunbound/ajocredit/issues/59).** The section applies to consumer credit lending. A rotating savings contribution may not be a regulated credit agreement. Delay Cover and Early Payout may be. [#59](https://github.com/abelunbound/ajocredit/issues/59) already blocks those two products for real members and keeps fees at £0 until a licence or a lender is in place. Until that gate closes, [#52](https://github.com/abelunbound/ajocredit/issues/52) is still built, because M3 asks for the band before a member joins, and the result must not be described as a finished CONC assessment.

Consumer Duty is already called out in the threat model for clear communication, fair value, foreseeable harm, and members in vulnerable circumstances. This research does not restate it as a new legal opinion.

## Open Banking and a bureau, side by side

| | TrueLayer, income and spending | Bureau commitments |
|---|---|---|
| What it sees | The accounts the member consents to, for the access window the bank allows | Credit agreements members of that bureau have supplied. Rent only where a rent reporter has supplied it. Not a full picture of every lender |
| What it is good for | A current view of pay in and pay out, including commitments that never reached a bureau | Agreed credit payments, arrears, and a history the member's current account may no longer show |
| What it misses | Cash income, another bank the member did not connect, a joint account we cannot attribute | A brand-new job, a commitment with a firm that does not report, a circle contribution at another club |
| What we store | Band, maximum pence, reasons | The same decision record, plus the search reference. Not the report |
| Member effect | Consent at the bank. One-time access is the default | A search may leave a footprint. The search type is unconfirmed. See [credit-bureau.md](credit-bureau.md) |
| When it runs | Before join, and again before a contribution increase that the stored maximum does not already allow | Same decision, and only if the contract and the consent exist |

Use both when both are available. If the bureau gate is still open, the band is computed from the bank summary alone and the reason list says the bureau was not searched. Do not block a dummy join on a bureau that we cannot call. Do not pretend a bank-only band is a CONC assessment.

The rules themselves, the numeric thresholds, are not in [#52](https://github.com/abelunbound/ajocredit/issues/52) and are not invented here. A later change writes them down in one place the server reads, with tests. Examples of the kind of rule that ticket has to choose, without numbers: income net of observed commitments, a floor for essential spending, and a maximum contribution that is a fraction of what is left. The fraction is an open product question.

A decline is any outcome where the rules would set the maximum contribution below the circle's minimum, or would refuse the join. That case waits for a person. The member is told the reason and how to ask for a review (SR-21, threat T-31). The person can record a different maximum and a reason. They cannot turn the result into a bare pass or fail flag. A low band with a small maximum is a successful calculation, not a decline.

## End to end

1. The member finishes identity verification ([#50](https://github.com/abelunbound/ajocredit/issues/50)) and connects TrueLayer ([#43](https://github.com/abelunbound/ajocredit/issues/43)), as in [truelayer.md](truelayer.md).
2. The server loads transactions in memory, converts money to integer pence without a binary float, and drops the payload.
3. If a bureau search is allowed, the server adds committed payments from the search, then drops the report.
4. The server computes the band, the maximum contribution in pence, and reason codes. The same inputs always produce the same outputs. The client does not send the band.
5. The server stores that result against the member ref, with `assessed_at` from `clock.now()`. It audits `consent_given` when the member consents, and `financial_data_viewed` when a platform admin opens the result.
6. Join, and any later rise in the contribution, is rejected by the server when the amount is above the stored maximum. The circle minimum and the member maximum are both enforced. A second circle shares the same maximum. Splitting the maximum across circles is an open question.
7. Early payout and Delay Cover read the same stored result. They do not pull the bank again unless the consent was one-time and has expired, in which case the member connects again. [#61](https://github.com/abelunbound/ajocredit/issues/61) still caps an early payout by cash already paid in, even when the band would allow more.
8. A person reviewing a decline sees the band, the reasons, and the maximum. They do not see raw transactions, because those were not stored. If they need a new look at the bank, the member consents again.

## Ledger, circles, and members

Affordability does not post a journal entry. The maximum is a gate on later money movement, not a balance.

The stored result proposed for [#52](https://github.com/abelunbound/ajocredit/issues/52):

| Field | Notes |
|---|---|
| `member_ref` | Synthetic in every test |
| `band` | A small set of labels the rules define. Not `pass` or `fail` |
| `max_contribution_pence` | Positive integer, or zero when the person has agreed the member should not contribute |
| `reason_codes` | Stable codes, plus a short text the member can read |
| `inputs` | Which sources ran: `truelayer`, `bureau`, or both. Not the source payload |
| `bureau_search_ref` | Empty when no search was made |
| `assessed_at` | `clock.now()` |
| `reviewed_by` | Set when a person reviews a decline. Empty on an ordinary band |

There is no table for this yet. Adding it is [#52](https://github.com/abelunbound/ajocredit/issues/52), not this docs change.

Reconciliation is: every join has a stored result newer than the consent, the contribution on the circle is less than or equal to `max_contribution_pence`, and a decline has a `reviewed_by` value before the member is allowed in. No Modulr balance is involved.

Circle admins see that a member is within the maximum or that a review is pending. They do not see income, transactions, or bureau fields. Other members see neither.

## Sandbox and test steps

No new supplier account is required for the rules themselves.

1. Follow [truelayer.md](truelayer.md) and connect Mock Bank (`providers=uk-cs-mock`, TrueLayer's published fictitious user). Pull the sample transactions.
2. Run the rules on that sample in a local process. Write the band, the maximum pence, and the reasons. Confirm the transaction payload is not in the database and not in the log.
3. Feed a second fixture that would put the maximum under the circle minimum. Confirm the join waits for review, the member sees a reason, and the stored result is still not `pass` or `fail`.
4. Bureau fixtures stay synthetic, as in [credit-bureau.md](credit-bureau.md). A missing bureau is a reason code, not an exception, until [#66](https://github.com/abelunbound/ajocredit/issues/66).
5. Assert in tests, when [#52](https://github.com/abelunbound/ajocredit/issues/52) is built, that ethnicity is unread, that a raw transaction string is absent from the row, and that a contribution above the maximum is rejected.

Do not use a personal bank account for the test. Do not commit a TrueLayer response body.

## Keys and config

TrueLayer and bureau credentials are listed in those documents. Affordability adds no key of its own. The rules belong in reviewed server config when they are written, not in the Dash client and not in git as a secret. A threshold is not a secret, but it is a product decision and should change in a reviewed pull request, in the same spirit as the fee switch (SR-28).

Environment split:

| `AJO_ENV` | Behaviour |
|---|---|
| `local` or `dev` | Mock Bank or a checked-in synthetic fixture. No live bureau |
| `ci` | Synthetic fixture only. No outbound call |
| production | Live TrueLayer only after [#143](https://github.com/abelunbound/ajocredit/issues/143). Live bureau only after [#66](https://github.com/abelunbound/ajocredit/issues/66) and [#65](https://github.com/abelunbound/ajocredit/issues/65) |

## Risks and open questions

- Applying CONC 5.2A before [#59](https://github.com/abelunbound/ajocredit/issues/59) is decided would overstate our permission. Skipping the band would break [#52](https://github.com/abelunbound/ajocredit/issues/52). Build the band, and label it as our join rule.
- The numeric rules are not chosen. Two people can disagree on a fair maximum. That choice needs a product owner and, if the adviser says CONC applies, a record of why the rule is proportionate.
- Open Banking misses cash and second banks. A bureau misses non-reporters. The reason codes have to say which source was missing so a reviewer does not treat silence as zero spending or zero debt.
- A footprint from a credit search is a member harm if the search type is wrong. Unconfirmed.
- Storing too much "for the reviewer" recreates the raw-transaction problem [#52](https://github.com/abelunbound/ajocredit/issues/52) forbids. Reviewers see codes and the maximum. A fresh consent is how they see the bank again.
- One maximum across several circles is undecided. Enforcing it per circle would let a member take on more than the rules allowed.
- Human review that never happens is an automated refusal. The queue needs an owner before real members join. [#65](https://github.com/abelunbound/ajocredit/issues/65) covers the data in that queue.
- Vulnerable-customer handling is named in the threat model and is not specified as a rule here. Open question for the adviser and for product.

## Tickets

| Ticket | How this document maps |
|---|---|
| [#52](https://github.com/abelunbound/ajocredit/issues/52) | The band, the maximum, the reasons, no raw transactions, human review, not pass or fail |
| [#43](https://github.com/abelunbound/ajocredit/issues/43) | TrueLayer connection that feeds the rules |
| [#50](https://github.com/abelunbound/ajocredit/issues/50) | Identity match before the band is relied on |
| [#56](https://github.com/abelunbound/ajocredit/issues/56), [#66](https://github.com/abelunbound/ajocredit/issues/66) | Reporting is a later monthly file, not this decision |
| [#59](https://github.com/abelunbound/ajocredit/issues/59) | Whether CONC 5.2A applies |
| [#65](https://github.com/abelunbound/ajocredit/issues/65) | DPIA before real bank or bureau data |
| [#61](https://github.com/abelunbound/ajocredit/issues/61), [#63](https://github.com/abelunbound/ajocredit/issues/63) | Early payout and Delay Cover read the stored maximum and still follow their own caps |
| [#144](https://github.com/abelunbound/ajocredit/issues/144) | Live credit page stops showing sample bureau data |

## Sources

- [CONC 5.2A Creditworthiness assessment](https://handbook.fca.org.uk/handbook/conc5/conc5s6)
- [FCA: creditworthiness and affordability, common misunderstandings](https://www.fca.org.uk/firms/creditworthiness-and-affordability-common-misunderstandings)
- [PS18/19: Assessing creditworthiness in consumer credit](https://www.fca.org.uk/publications/policy-statements/ps18-19-assessing-creditworthiness-consumer-credit)
- [PS18/19 PDF](https://www.fca.org.uk/publication/policy/ps18-19.pdf)
- TrueLayer and bureau pages are listed in [truelayer.md](truelayer.md) and [credit-bureau.md](credit-bureau.md)
