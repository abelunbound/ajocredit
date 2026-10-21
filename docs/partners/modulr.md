# Modulr

Research date: 21 October 2026. Modulr holds and moves circle money. Ajo's ledger records the same events in integer pence. This document is the research for that integration. No Modulr client is added here.

Modulr is not a bank. Modulr FS Ltd (FRN 900573) is an authorised e-money institution, regulated by the FCA. Modulr Finance Limited (FRN 900699) is registered as its e-money agent. Customer funds received in exchange for e-money are safeguarded: they are segregated from Modulr's own corporate funds and cannot be used for Modulr's other purposes. Safeguarded funds are held at credit institutions, at the Bank of England, or in FCA-approved liquid assets. The FSCS does not apply. An insolvency practitioner returns safeguarded funds and may deduct costs if those costs cannot be met from elsewhere. Source: [UK Safeguarding Information](https://www.modulrfinance.com/uk-safeguarding-information).

The threat model already says member money does not sit in Ajo's own bank account. Contributions go to the regulated partner. See [docs/security/THREAT_MODEL.md](../security/THREAT_MODEL.md) (assets A-01, control SR-27, gate [#62](https://github.com/abelunbound/ajocredit/issues/62)).

## What is useful for Ajo

Public docs itemised against our milestones:

| Modulr capability | Why Ajo needs it | Source |
|---|---|---|
| GBP account per customer, with its own sort code and account number | A circle needs a place members can pay into, without sharing personal bank details with each other | [Accounts](https://modulr.readme.io/docs/account), [Create account](https://modulr.readme.io/reference/createaccount) |
| External reference, up to 50 characters (letters, numbers, underscore, hyphen, space) | Store the synthetic `circle_ref` on the Modulr account so a webhook can be tied to a circle | [Create account](https://modulr.readme.io/reference/createaccount) |
| Partner mode, which can be enabled in sandbox so we can manage customers | One Ajo legal entity opening an account per circle | [Getting Sandbox Access](https://modulr.readme.io/docs/gaining-use-of-the-api), [Partner portal](https://knowledge.modulrfinance.com/knowledge-hub/partner-portal-overview) |
| Direct Debit collections into a collection account, with mandates and collection schedules | Monthly contributions by direct debit ([#51](https://github.com/abelunbound/ajocredit/issues/51)) | [Direct Debit Collections (UK)](https://modulr.readme.io/docs/direct-debit-collections-1), [Getting started](https://modulr.readme.io/docs/what-is-dd-collections), [Starting Collections](https://modulr.readme.io/docs/starting-collections) |
| Pay-in notifications | A bank transfer into the circle account | Webhook types include `PAYIN` on [customer webhook subscription](https://modulr.readme.io/reference/addcustomerwebhooknotificationsubscription) |
| Payments out of an account | The monthly payout ([#54](https://github.com/abelunbound/ajocredit/issues/54)) and an accepted early payout ([#57](https://github.com/abelunbound/ajocredit/issues/57)). Sandbox includes "Manage payments" | [Getting Sandbox Access](https://modulr.readme.io/docs/gaining-use-of-the-api) |
| Webhooks signed with an HMAC secret of exactly 32 characters, with retries | Credit the ledger only after the signature checks, and ignore a repeat | [Setting up a webhook](https://modulr.readme.io/docs/channel-manager-setting-up-a-webhook) |
| Sandbox-only credit of fictitious money | Test a pay-in without a real bank | [Getting Sandbox Access](https://modulr.readme.io/docs/gaining-use-of-the-api) |

The public API docs call these **accounts**. They return a sort code and account number for GBP. The Ajo threat model calls the partner accounts virtual accounts. This research did not find a separate Modulr product, in the API docs read, whose name is "virtual account" as distinct from an account. Confirm the commercial name with Modulr. That is an open question.

A different direct-debit guide, [Receiving DD Collections](https://modulr.readme.io/docs/receiving-dd-collections), describes a merchant pulling money **out** of a Modulr account. That is the opposite direction from a member's high-street bank paying a contribution in. Contribution direct debits follow the collection guide above, not that outbound guide.

## Platform reserve account, and client money

**(a) Is there a platform master or operating account, tied to the platform admin, used to fund Delay Cover and Early Payout? How is it separated from client or safeguarded funds?**

The public docs do not describe a product called a platform master account, and they do not tie an account to an Ajo `platform_admin` user.

What they do describe:

- A new sandbox is a **Direct Customer** with API credentials, portal admin-user credentials, and **one GBP account credited with £50,000 of fictitious money**. Source: [Getting Sandbox Access](https://modulr.readme.io/docs/gaining-use-of-the-api).
- Modulr can reconfigure that sandbox as a **Partner**, which adds the ability to manage customers. The same page.
- Safeguarding separates **Modulr's customers' e-money** from **Modulr's own corporate funds**. It is Modulr's segregation duty. It is not a description of an Ajo operating account sitting outside safeguarding while member balances sit inside it. Source: [UK Safeguarding Information](https://www.modulrfinance.com/uk-safeguarding-information).
- Introduced-client terms retrieved from [this Modulr PDF](https://2270724.fs1.hubspotusercontent-na1.net/hubfs/2270724/Customer%20Communications/APP%20Fraud_Sept%2024/Introduced%20Client_Account%20Terms%20and%20Conditions_23-09-24.pdf) say an internal transfer from another account owned or controlled by the partner platform applies instantly, that the FSCS does not apply, and that client funds are safeguarded under the Electronic Money Regulations 2011. Those terms are for an account the partner platform opens for an introduced client. They were not read as permission for Ajo to treat one account as unsafeguarded operating capital.

The Ajo recommendation, which is our bookkeeping proposal and not a Modulr product claim:

- Open a separate Modulr GBP account whose external reference is `platform-reserve`.
- Ledger it as `asset:platform:reserve` (asset, GBP, no `circle_ref`, no `member_ref`).
- Use it to fund a Delay Cover top-up ([#63](https://github.com/abelunbound/ajocredit/issues/63)).
- Do not attach member contribution mandates to it, and do not pay routine circle contributions into it.
- The Ajo `platform_admin` role may read `GET /admin/ledger`. That role does not own the Modulr account. Portal admin credentials stay in the secrets store.

An accepted early payout is capped by the amount that member has already paid in ([#61](https://github.com/abelunbound/ajocredit/issues/61)). That cash is already in the circle account, so the payout is made from the circle account. Draw the reserve for an early payout only when the circle account is short of that amount. A shortfall of that kind is a reconciliation break to resolve first, or a larger advance than the cap allows. A larger advance stays behind the legal check ([#59](https://github.com/abelunbound/ajocredit/issues/59)).

**Separation still to be decided by a human adviser.** Modulr safeguards the e-money it has issued. Once Ajo's reserve cash and members' contributions are both balances on Modulr accounts, both may be safeguarded client money. Whether the reserve is Ajo's own money, client money, or a mixture, and whether moving it into a circle account changes that, is not answered by the pages above. The same adviser question covers safeguarding, client money, and the fee-free credit exemption in [#59](https://github.com/abelunbound/ajocredit/issues/59). Do not place member funds in a bank account in Ajo's own name while that question is open.

## One Modulr account per circle

**(b) Does each Ajo get its own Modulr account? What about one account per member, or one pooled account?**

Recommendation: **one Modulr GBP account per circle**, plus the single reserve account above, plus a dedicated direct-debit collection account if Modulr requires one. Do not open a Modulr account per member for the pilot. Do not use one pooled Modulr account for every circle.

| Arrangement | What the public docs allow us to say | Trade-off for Ajo |
|---|---|---|
| One account per circle | Create Account takes a customer id, an external reference, a currency, and a product code. A GBP account comes back with a sort code and account number. Sandbox direct customers can "manage accounts". Partner mode can "manage customers" | Matches the ledger. `asset:partner:{circle_ref}` is already one asset per circle ([docs/ledger.md](../ledger.md)). A pay-in lands on that circle's sort code. Reconciliation is that account's balance against that one ledger asset. Members of the circle see the circle account on their own statement. They do not see another member's personal bank account (SR-23) |
| One account per member | Not found as a required Modulr model. The partner portal page describes creating customers from business details, with Modulr or the partner doing KYC. It does not say a consumer member is a customer | Isolates each member at Modulr, at the cost of one KYC record and one account per member. The pot would have to be assembled by internal transfers before a payout. The ledger would no longer match one partner asset per circle. Whether Modulr will onboard each member as a consumer customer is an open question |
| One pooled account, circles only in the ledger | A single account can receive payments. The ledger can still split them by `circle_ref` | One Modulr balance has to equal the sum of every circle asset. A payment with the wrong reference is in the wrong circle until someone posts a reversal. The production direct-debit note says the collection account should not be used for any other inbound payments, so a pool that also takes bank transfers and direct debits conflicts with that note |

Product codes are agreed at onboarding. The docs give dummy examples such as `GBP-000001` for UK schemes, and say the real code comes from Modulr. Source: [Accounts](https://modulr.readme.io/docs/account).

`circle_ref` is up to 64 characters on `ledger_accounts` and the Modulr external reference is up to 50. Circle refs have to fit both. The synthetic refs used in the ledger docs, such as `circle-synth-example`, fit.

Direct debit adds a constraint. In production Modulr connects a Service User Number (SUN) to a collection account, and that account should not be used for any other inbound payments. Source: [Getting started with DD collections](https://modulr.readme.io/docs/what-is-dd-collections). Ask Modulr whether each circle account can be a collection account. If the answer is one shared collection account, bank-transfer pay-ins still go to the per-circle account, and a successful collection is transferred internally onto the circle account before the ledger treats it as that circle's money. The endpoint that moves money between two accounts we control was not confirmed in the pages read. The introduced-client terms describe instant internal transfers. The API name is an open question.

The Modulr account id is not a column on the ledger. Account codes are permanent, so the id must not be written into the code later. A future table, outside the append-only ledger, should map `circle_ref` to the Modulr account id. `ledger_entries.reference` stores the Modulr payment id for the event.

## End to end

Until [#62](https://github.com/abelunbound/ajocredit/issues/62) is closed, M4 to M6 are built against mocks. The steps below are the target flow once sandbox access exists.

1. A platform operator, not a circle member, creates the Modulr customer for the Ajo legal entity after Modulr's KYC (in-house or outsourced). Source: [Partner portal](https://knowledge.modulrfinance.com/knowledge-hub/partner-portal-overview).
2. Creating a circle calls Create Account with currency `GBP`, the onboarded product code, and `externalReference` set to the circle ref. The response account id is stored off the ledger. The ledger opens `asset:partner:{circle_ref}` if that code is not already open.
3. The member's payout destination is verified and then left alone for a waiting period ([#53](https://github.com/abelunbound/ajocredit/issues/53)). During the wait, payouts go to the previous verified account. Bank details are not ledger columns and are not returned to other members.
4. Contribution by bank transfer: the member pays the circle sort code and account number. Modulr sends a `PAYIN` webhook. We check the HMAC, then fetch the payment from Modulr's API, and only then post the ledger. Modulr's own duplicate guidance is to use `PaymentId` for `PAYIN` and `PAYOUT`, because a retry can change `EventId` and a failed payment can have an empty `TransactionId`. Source: [Setting up a webhook](https://modulr.readme.io/docs/channel-manager-setting-up-a-webhook).
5. Contribution by direct debit: the member completes a mandate, Ajo gives the advance notice the scheme requires, and a collection is scheduled. Modulr's published timeline credits the collection account on day 3 and sets the collection to success on day 5 if no Automated Return of Unpaid Direct Debit (ARUDD) arrives. Funds should be withdrawn only once the status is `SUCCESSFUL`. Source: [Starting Collections](https://modulr.readme.io/docs/starting-collections). The ledger posts the contribution at that success status, not on the day-3 credit. A return reverses nothing that was not posted. If a later ticket posts on day 3, the ARUDD must post a reversal. Waiting for success is the recommendation.
6. Monthly payout: the server selects the scheduled recipient and instructs a payment from the circle account to the verified destination ([#54](https://github.com/abelunbound/ajocredit/issues/54)). The webhook's `PaymentId` is the ledger reference.
7. Delay Cover: after the server-side limit and the double-submit check ([#58](https://github.com/abelunbound/ajocredit/issues/58)), move the missing contribution from `platform-reserve` to the circle account and post the entries below. Repayment is the next cycle or a direct debit retry ([#60](https://github.com/abelunbound/ajocredit/issues/60)).
8. Early payout: the quote is stored with an id and an expiry and is not posted ([#64](https://github.com/abelunbound/ajocredit/issues/64)). Accept sends the quote id. The payment is instructed once, from the circle account, for the capped amount ([#57](https://github.com/abelunbound/ajocredit/issues/57), [#61](https://github.com/abelunbound/ajocredit/issues/61)).

Suspicious patterns (many circles, fast in and out, a name that does not match) are escalated to Modulr's AML process. Payments go only through Modulr (SR-27, [#50](https://github.com/abelunbound/ajocredit/issues/50), [#51](https://github.com/abelunbound/ajocredit/issues/51)).

## Ledger

Amounts are integer pence. Every entry has at least two lines and debits equal credits. A correction is a reversal with `reversal_of_id` set, not an edit. `reference` is unique, so the same Modulr `PaymentId` cannot post twice. References have a 128-character limit. Confirm Modulr's payment id fits. That length was not stated on the webhook page.

The chart already used in code and in [docs/ledger.md](../ledger.md):

| Code | Kind | Meaning today |
|---|---|---|
| `asset:partner:{circle_ref}` | asset | Pence held for that circle at the partner |
| `liability:{member_ref}:{circle_ref}` | liability | Net pence that member has paid in and not yet been paid out |
| `expense:fee:{circle_ref}` | expense | Used by the balance-check seed. The pilot must not move cash for a fee |
| `equity:opening:{circle_ref}` | equity | Seed only |

Proposed codes for the reserve. They are not opened by this docs change:

| Code | Kind | Refs | Meaning |
|---|---|---|---|
| `asset:platform:reserve` | asset | none | Cash in the Modulr reserve account |
| `asset:receivable:{member_ref}:{circle_ref}` | asset | circle and member | What that member owes the reserve after Delay Cover |

A negative balance on a member liability means the circle has paid them more than they have paid in. The ledger does not forbid it. That is the ordinary position of a member who has already received the pot and still owes later contributions. The early-payout cap uses the credit balance only, floored at zero. It must ignore pence that came from the reserve.

Synthetic example. Circle `circle-synth-example`, member `member-ada`, contribution 2575 pence. This is the same shape as the contribution already in the ledger docs.

**Bank transfer or successful direct debit ([#51](https://github.com/abelunbound/ajocredit/issues/51))**

| Account | Direction | Pence |
|---|---|---|
| `asset:partner:circle-synth-example` | debit | 2575 |
| `liability:member-ada:circle-synth-example` | credit | 2575 |

`reference` is the Modulr `PaymentId`. Audit event `contribution_paid`, which is already a listed audit name. A late or missed month uses `contribution_late` or `contribution_missed` and does not post cash.

**Monthly payout ([#54](https://github.com/abelunbound/ajocredit/issues/54))**

| Account | Direction | Pence |
|---|---|---|
| `liability:{recipient}:{circle_ref}` | debit | payout |
| `asset:partner:{circle_ref}` | credit | payout |

Audit event `payout_sent`.

**Delay Cover top-up ([#63](https://github.com/abelunbound/ajocredit/issues/63))**

Four lines, one entry, so the circle cash rises, the reserve cash falls, and the member owes the reserve. The member liability is left unchanged, so the top-up does not count as money they have paid in.

| Account | Direction | Pence |
|---|---|---|
| `asset:partner:{circle_ref}` | debit | shortfall |
| `asset:platform:reserve` | credit | shortfall |
| `asset:receivable:{member_ref}:{circle_ref}` | debit | shortfall |
| `liability:pool:{circle_ref}` | credit | shortfall |

`liability:pool:{circle_ref}` is a proposed liability for cash the reserve has put into the pot. It is not a member. Audit event `delay_cover_drawn`. The request itself is `delay_cover_requested` and posts nothing.

This pool liability is a proposal because today's ledger docs treat the member liability as the only credit for a contribution. Implementers of [#63](https://github.com/abelunbound/ajocredit/issues/63) and [#61](https://github.com/abelunbound/ajocredit/issues/61) need to keep "already paid in" equal to the member's own credits.

**Repayment of the reserve ([#60](https://github.com/abelunbound/ajocredit/issues/60))**

When the retry or the extra part of the next contribution is `SUCCESSFUL`, and the cash has been placed in the reserve account:

| Account | Direction | Pence |
|---|---|---|
| `asset:platform:reserve` | debit | repaid |
| `asset:receivable:{member_ref}:{circle_ref}` | credit | repaid |

If the cash lands in the circle account first, a second entry moves it: debit the reserve, credit the circle asset. The member's ordinary contribution for that month is still the two-line contribution entry, separate from the repayment.

**Early payout on accept ([#57](https://github.com/abelunbound/ajocredit/issues/57))**

| Account | Direction | Pence |
|---|---|---|
| `liability:{member_ref}:{circle_ref}` | debit | capped amount |
| `asset:partner:{circle_ref}` | credit | capped amount |

The quote audit events are `early_payout_quoted` and `early_payout_accepted`. The quote row is not a ledger entry. The payment uses an idempotency key that becomes `reference`.

**Fee**

[#58](https://github.com/abelunbound/ajocredit/issues/58) says the fee is calculated and recorded, and the charge is £0. The ledger rejects a line of zero pence. A £0 charge therefore cannot be a ledger line. Record the calculated fee and the £0 charge on the quote and in the audit log. Do not post a cash fee. Whether a later ticket should also post a pair of equal fee expense and fee waiver entries, which would net to zero cash, is an open question for [#58](https://github.com/abelunbound/ajocredit/issues/58). Any non-zero charge stays behind [#59](https://github.com/abelunbound/ajocredit/issues/59).

### Reconciliation

SR-18 asks for a scheduled balance check against the partner.

1. For each circle, read the Modulr account and compare it with the signed balance of `asset:partner:{circle_ref}`. Compare the reserve account with `asset:platform:reserve`.
2. Convert Modulr's amount to integer pence without a binary float. The unit of the balance field (pence or pounds) was not confirmed on the account page read. Confirm it before coding. That is an open question.
3. Direct-debit cash credited on day 3 and not yet `SUCCESSFUL` is in transit. Keep it off the contribution entry until day 5, or the circle asset will be ahead of money Modulr may still return.
4. A mismatch alerts. It does not auto-edit the ledger. A confirmed partner reversal is a new reversing entry.
5. Webhook HMAC is checked before any post. A `2xx` response means we accepted the HTTP call. Modulr retries a non-`2xx` up to five times (1 minute, 5 minutes, 25 minutes, 2 hours 5 minutes, 10 hours 25 minutes). Source: [Setting up a webhook](https://modulr.readme.io/docs/channel-manager-setting-up-a-webhook). The unique `reference` is what stops a retry posting twice.
6. [#142](https://github.com/abelunbound/ajocredit/issues/142) asks for one real contribution and one real payout to reconcile before alpha. [#146](https://github.com/abelunbound/ajocredit/issues/146) asks for a live circle to reconcile after each payout.

## Members and circles

- The circle admin is the creator of that Ajo. They can see payout status for the circle. They cannot move the reserve. Reserve movement is a server-side posting, audited.
- A member pays into the circle's Modulr account. The API continues to return other members' names and payment status only (SR-23, [#48](https://github.com/abelunbound/ajocredit/issues/48) is the privacy ticket named in the threat model).
- A member who has been paid and then leaves still owes the remaining contributions. Direct debit continues, or Delay Cover fills the pot and the receivable remains ([#47](https://github.com/abelunbound/ajocredit/issues/47) in the threat model). A replacement takes unpaid positions only.
- One person with several memberships is flagged from identity, device, bank account, or Open Banking account ([#50](https://github.com/abelunbound/ajocredit/issues/50)). The Modulr account per circle does not by itself stop that. The payable destination and the mandate account are inputs to that flag.

## Sandbox

Gate [#62](https://github.com/abelunbound/ajocredit/issues/62): do not point a deployed environment at sandbox or live Modulr until that access exists. Local and CI tests keep using the ledger seed and mocks.

1. Register from the form linked on [Getting Sandbox Access](https://modulr.readme.io/docs/gaining-use-of-the-api) ("complete the form here"). The href of that form was not in the page text extracted for this research. The sandbox portal sign-in is [https://secure-sandbox.modulrfinance.com/](https://secure-sandbox.modulrfinance.com/).
2. The default sandbox is a Direct Customer: API credentials, an admin user, and one GBP account with £50,000 fictitious money. Ask Modulr to enable Partner mode (manage customers) and Direct Debit collections. Direct debit setup is a separate request: they provide a dedicated collection account and the permission to use it. Source: [Getting started with DD collections](https://modulr.readme.io/docs/what-is-dd-collections).
3. Sandbox keys may be limited to one month. Production API access is IP-restricted. HMAC is the only production authentication. Sandbox also offers a token URL. Sources: [Security](https://modulr.readme.io/docs/security), [API base URLs](https://modulr.readme.io/docs/api-base-urls).
4. Base URLs from that page:
   - HMAC sandbox: `https://api-sandbox.modulrfinance.com/api-sandbox/`
   - Token sandbox: `https://api-sandbox.modulrfinance.com/api-sandbox-token/`
   - Production URL: given at onboarding, not published on that page.
5. Put the key and HMAC secret in `.env` on one machine, or in GitHub Actions secrets for a job that is allowed to call sandbox. Never commit them. Never paste them into an issue.
6. Credit fictitious money with the sandbox-only credit endpoint named on the sandbox page. The path of that endpoint was not copied here because this research did not open its reference page.
7. Create a customer if Partner mode is on, create a GBP account with a synthetic external reference such as `circle-synth-example`, credit it, send a test payment, and confirm a signed webhook. Post the matching ledger entry in a local database only, with synthetic refs.
8. For direct debit, follow Modulr's sandbox collection guide after they enable it. Use their test payer details. Do not use a real sort code or a real account number.
9. A webhook listener on a laptop must not be exposed as a production URL. Use a tunnel only on a machine with sandbox keys, and a 32-character HMAC secret that is not a real production secret.

Signing the HMAC is specified on Modulr's authentication page, linked from [Security](https://modulr.readme.io/docs/security). Implement that page when the client is built. This research does not copy the signing steps into the repo.

## Keys and config

Intended variables, for the ticket that builds the client. Not added to `.env.example` in this change.

| Name | Where | Notes |
|---|---|---|
| `MODULR_API_KEY` | `.env`, GitHub Actions secret, or the production secrets manager | Sandbox or live key. Not a code constant |
| `MODULR_HMAC_SECRET` | same | Production requires HMAC. Sandbox token auth is not used in production |
| `MODULR_BASE_URL` | same | One of the sandbox URLs above, or the production URL from onboarding |
| `MODULR_WEBHOOK_SECRET` | same | Exactly 32 characters, the webhook HMAC secret |
| `MODULR_WEBHOOK_HMAC_ALG` | config, not a secret | One of the algorithms Modulr lists: `hmac-sha1`, `hmac-sha256`, `hmac-sha384`, `hmac-sha512` |
| `MODULR_PRODUCT_CODE` | config | The code Modulr issues. The docs' `GBP-000001` is a dummy example |
| `MODULR_CUSTOMER_ID` | secret or config | The platform customer id. Not a member id |

CI today has no Modulr secrets and should stay that way until a test is written to use them. [#145](https://github.com/abelunbound/ajocredit/issues/145) puts live keys in the production secrets manager only. [#142](https://github.com/abelunbound/ajocredit/issues/142) refuses sandbox credentials when `AJO_ENV=production`.

`AJO_ENV` remains the switch the rest of the app already uses. A local process uses sandbox or a mock. Production uses the live URL from onboarding.

## Risks and open questions

Regulatory, for a human adviser, not for this research to decide:

- Is a circle balance client money, and is the reserve the same kind of money once it sits at Modulr?
- Does Delay Cover or Early Payout make Ajo a creditor, an e-money distributor, or an introducer? [#59](https://github.com/abelunbound/ajocredit/issues/59) already blocks real-member use of those products and keeps the fee at £0.
- The FSCS does not cover Modulr e-money. Members need to be told that in the terms, once an adviser has approved the wording. [#65](https://github.com/abelunbound/ajocredit/issues/65) covers the personal-data side of the same go-live.
- Modulr will KYC the customer. Which legal person is the customer for a circle (Ajo, the circle admin, or each member) is an open question. The recommendation above makes the Ajo legal entity the customer.

Product and technical:

- Confirm "account" is the contracted name for what our threat model calls a virtual account.
- Can one customer hold many GBP accounts, and can each be a direct-debit collection account?
- Which API moves funds between our own accounts?
- What unit do account balances and payment amounts use, and does a payment id fit in 128 characters?
- Day-3 direct-debit credit can still be returned on day 5. Posting early will overstate the circle.
- Webhook retries and a non-unique `EventId` will double-credit a member if `reference` is not the `PaymentId`.
- Sandbox keys can expire after a month. A CI job that calls sandbox will start failing when they do.
- Production is IP-allowlisted. The deployed egress addresses have to be given to Modulr at onboarding.
- The partner portal's customer-creation guide is written for businesses. Consumer members as Modulr customers are unconfirmed.
- Fee recording in the ledger cannot be a zero-pence line. See the fee section above.

## Tickets

| Ticket | How this document maps |
|---|---|
| [#51](https://github.com/abelunbound/ajocredit/issues/51) | Direct debit and bank-transfer contributions, ledger on confirmed pay-in |
| [#54](https://github.com/abelunbound/ajocredit/issues/54) | Payout from the circle account to that month's recipient |
| [#53](https://github.com/abelunbound/ajocredit/issues/53) | Payout destination change: step-up, wait, then Modulr pays the verified account |
| [#63](https://github.com/abelunbound/ajocredit/issues/63) | Reserve account tops up the circle |
| [#58](https://github.com/abelunbound/ajocredit/issues/58), [#60](https://github.com/abelunbound/ajocredit/issues/60) | Limits, double-submit, £0 fee, repayment |
| [#64](https://github.com/abelunbound/ajocredit/issues/64), [#57](https://github.com/abelunbound/ajocredit/issues/57), [#61](https://github.com/abelunbound/ajocredit/issues/61) | Quote, then one payout from the circle account, capped by cash already paid in |
| [#62](https://github.com/abelunbound/ajocredit/issues/62) | Sandbox access gate |
| [#59](https://github.com/abelunbound/ajocredit/issues/59) | Fee-free exemption gate before real Delay Cover or Early Payout |
| [#142](https://github.com/abelunbound/ajocredit/issues/142), [#145](https://github.com/abelunbound/ajocredit/issues/145), [#146](https://github.com/abelunbound/ajocredit/issues/146) | Live credentials, one reconciled contribution and payout, then a live circle |

## Sources

- [UK Safeguarding Information](https://www.modulrfinance.com/uk-safeguarding-information)
- [Getting Sandbox Access](https://modulr.readme.io/docs/gaining-use-of-the-api)
- [API base URLs and authentication](https://modulr.readme.io/docs/api-base-urls)
- [Security](https://modulr.readme.io/docs/security)
- [Accounts](https://modulr.readme.io/docs/account)
- [Create account](https://modulr.readme.io/reference/createaccount)
- [Partner portal overview](https://knowledge.modulrfinance.com/knowledge-hub/partner-portal-overview)
- [Direct Debit Collections (UK - GBP)](https://modulr.readme.io/docs/direct-debit-collections-1)
- [Getting started with Direct Debit collections](https://modulr.readme.io/docs/what-is-dd-collections)
- [Starting Collections](https://modulr.readme.io/docs/starting-collections)
- [Receiving DD Collections](https://modulr.readme.io/docs/receiving-dd-collections) (outbound from a Modulr account; not the contribution flow)
- [Setting up a webhook](https://modulr.readme.io/docs/channel-manager-setting-up-a-webhook)
- [Customer webhook subscription](https://modulr.readme.io/reference/addcustomerwebhooknotificationsubscription)
- [Introduced client account terms PDF, 23 September 2024](https://2270724.fs1.hubspotusercontent-na1.net/hubfs/2270724/Customer%20Communications/APP%20Fraud_Sept%2024/Introduced%20Client_Account%20Terms%20and%20Conditions_23-09-24.pdf)
- [Sandbox portal](https://secure-sandbox.modulrfinance.com/)
