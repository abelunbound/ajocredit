# TrueLayer

Research date: 21 October 2026. TrueLayer is the read-only view of a member's own bank. Modulr moves circle money. TrueLayer does not post ledger cash.

TrueLayer's current Data docs describe two integrations. [Data API basics](https://docs.truelayer.com/docs/data-api-basics) says a first integration should use Data API v3, and that v1 and v3 cover the same use cases with different flows. The sandbox quickstart that names Mock Bank still uses an auth link and an authorisation code. Both are recorded below. Which of the two sandbox paths a new UK affordability app should implement is an open question to confirm against the docs on the day the client is built ([#43](https://github.com/abelunbound/ajocredit/issues/43)).

## What is useful for Ajo

| Capability | Why Ajo needs it | Source |
|---|---|---|
| Account holder name, account number, sort code, IBAN | Match the connected account to the verified identity before the member joins or is paid (SR-20, SR-21) | [Enable your users to connect their bank account](https://docs.truelayer.com/docs/enable-your-users-to-connect-their-bank-account) |
| Transactions and balances | Income and spending inputs to the affordability band ([#52](https://github.com/abelunbound/ajocredit/issues/52)). Data v3 lists affordability as a use case and asks for scopes `info`, `accounts`, and `transactions` | Same page |
| `one_time` data access | One check at join, or before a later increase, without a standing feed | Same page. How long `one_time` lasts depends on the bank |
| Verification API | Compare a name we already hold with the name on the connected account, and return a `match_score` from 0 to 100 | [Verification API basics](https://docs.truelayer.com/docs/verification-api-basics), [Verify an account](https://docs.truelayer.com/docs/verify-an-account) |
| Account-holder verification of a name plus an account identifier | Check a payout destination the member typed, without pulling their transactions ([#53](https://github.com/abelunbound/ajocredit/issues/53)) | [Account holder verification](https://docs.truelayer.com/docs/account-holder-verification-1) |
| Mock Bank in sandbox | Exercise the connection with fictitious credentials | [Quickstart: Retrieve test bank data](https://docs.truelayer.com/docs/quickstart-retrieve-bank-data) |

Data v3, on the page read, is supported in the UK only. Scopes on that page are `info`, `accounts`, and `transactions`. The v1 scope list also has `balance`, `cards`, `direct_debits`, `standing_orders`, and `offline_access`. Source: [General Data API concepts](https://docs.truelayer.com/docs/general-data-api-concepts). Ajo does not need cards. Direct debits and standing orders would show commitments, and transactions already show money leaving the account. Prefer the three v3 affordability scopes. Add further scopes only if the rules in [#52](https://github.com/abelunbound/ajocredit/issues/52) cannot see a commitment any other way.

The Verification API is in public beta in the UK, Germany, and Spain. TrueLayer asks integrators to contact support with the `client_id` before using it. Source: [Verification API basics](https://docs.truelayer.com/docs/verification-api-basics).

TrueLayer also has a Payments API and a sandbox for it ([Test payments in sandbox](https://docs.truelayer.com/docs/test-payments-in-sandbox)). Circle contributions and payouts go through Modulr, so that payments product is not part of this design. Using both to move the same funds would split reconciliation across two providers.

## End to end

1. The member has an Ajo account and has passed dummy identity verification ([#50](https://github.com/abelunbound/ajocredit/issues/50)), or is in that flow.
2. The server starts a TrueLayer connection with the affordability scopes, `data_access_type` `one_time` if we are on Data v3, and a `state` value that is our own member ref. `state` comes back on the redirect so the code is tied to that member. Source: [Quickstart: Retrieve test bank data](https://docs.truelayer.com/docs/quickstart-retrieve-bank-data).
3. The member consents at their bank. TrueLayer redirects to a URI registered on the app. The redirect carries a code, not the transactions.
4. The server exchanges the code, or, on Data v3, uses the connection id with a client-credentials token that has the `data` scope. Source: [Enable your users to connect their bank account](https://docs.truelayer.com/docs/enable-your-users-to-connect-their-bank-account), [Create a connection](https://docs.truelayer.com/docs/create-a-connection-v3).
5. The server reads identity, accounts, and transactions in memory. It compares the account-holder name with the verified identity. A mismatch stops the join. The same open-banking account on two Ajo users is an input to the duplicate-person flag ([#50](https://github.com/abelunbound/ajocredit/issues/50), SR-22).
6. The affordability rules in [affordability.md](affordability.md) reduce the feed to a band, a maximum contribution in pence, and reasons. The raw transactions are discarded. They are not written to the database, the audit log, or application logs (SR-21, [#52](https://github.com/abelunbound/ajocredit/issues/52)).
7. Tokens are stored encrypted, with the key outside the database ([#43](https://github.com/abelunbound/ajocredit/issues/43), SR-19). `offline_access` and a refresh token are requested only when a person has decided we need a later pull. The default check is one-time.
8. A payout-destination change ([#53](https://github.com/abelunbound/ajocredit/issues/53)) can use account-holder verification (name plus account identifier) instead of a full transaction pull. The member still has the step-up and the waiting period in that ticket. During the wait, Modulr pays the previous destination.
9. Consent withdrawal uses the existing audit name `consent_withdrawn`. The encrypted token is dropped and no further pull is made.

[#143](https://github.com/abelunbound/ajocredit/issues/143) is the later switch from sandbox to live: live client id and secret in the production secrets manager, redirect URIs on the live domain, and production refusing to start with sandbox credentials.

## Ledger, circles, and members

TrueLayer does not debit or credit a ledger account. A connection, a name match, and an affordability result are not money moving.

What is stored, when [#43](https://github.com/abelunbound/ajocredit/issues/43) and [#52](https://github.com/abelunbound/ajocredit/issues/52) are built:

| Stored | Not stored |
|---|---|
| Member ref, connection id, consent time from `clock.now()`, scopes, `one_time` or `recurring` | Raw transactions, running balances, merchant names |
| Encrypted access token, and a refresh token only if `offline_access` was requested | Token in logs, in the ledger, or in git |
| Name-match result and score | Full account number in the audit log |
| Affordability band, maximum contribution in pence, reason codes | A copy of the TrueLayer payload |

The audit log already has `consent_given`, `consent_withdrawn`, and `financial_data_viewed`. A view of the band by a platform admin uses `financial_data_viewed`. The band is an attribute of the member, not of one circle. Each circle membership must still respect that member's maximum contribution. Two circles cannot add up to more than the maximum. How the maximum is split across circles is an open question for [#52](https://github.com/abelunbound/ajocredit/issues/52).

Reconciliation here means the connection id on our row matches a connection TrueLayer still recognises, and a second delivery of the same redirect does not create a second consent. It does not mean a balance tie-out. Circle balances tie out to Modulr, in [modulr.md](modulr.md).

Data v3 access tokens for the client are obtained with `grant_type=client_credentials` and the `data` scope, posted to `https://auth.truelayer.com/connect/token`. Calls then send `Connection-Id`. Source: [Enable your users to connect their bank account](https://docs.truelayer.com/docs/enable-your-users-to-connect-their-bank-account).

## Sandbox

1. Create a Console account. A new account is in sandbox and does not move live money. Sign-up is email and password, or Google or GitHub single sign-on. Source: [Quickstart: Create a Console account](https://docs.truelayer.com/docs/quickstart-create-a-console-account).
2. Create an app. The sandbox `client_id` is prefixed `sandbox-`. It is 4 to 30 lowercase letters and numbers in the part you choose, and it cannot be changed. Download the client secret once and store it outside the repo. Sandbox credentials only mint sandbox tokens.
3. Register the redirect URI exactly, including `https://`. For a browser test, TrueLayer documents `https://console.truelayer.com/redirect-page`, which shows the code on screen.
4. Build an auth link. Required parameters are `response_type=code`, `client_id`, `redirect_uri`, and `scope`. Add `state`. For Mock Bank add `providers=uk-cs-mock`. Source: [Quickstart: Retrieve test bank data](https://docs.truelayer.com/docs/quickstart-retrieve-bank-data).

Example shape, with a placeholder client id, not a real one:

```text
https://auth.truelayer.com/?response_type=code&client_id=sandbox-example&redirect_uri=https://console.truelayer.com/redirect-page&scope=info%20accounts%20balance%20transactions&state=member-ada&providers=uk-cs-mock
```

5. Open the link, choose Mock Bank, and sign in with TrueLayer's published fictitious user. The quickstart gives username `john` and password `doe` as an example. Those are Mock Bank credentials, not an Ajo account.
6. Exchange the code for an access token using the sandbox Data collection, or the token endpoint in the docs. If `offline_access` was granted, the response includes a refresh token. Do not enable that for the default affordability check.
7. Call the accounts endpoint with the bearer token. Confirm the sample payload is synthetic. Run the affordability rules on it, write down the band and reasons, and do not save the transactions.
8. Data API hosts on the payments sandbox page, which publishes the same host split: sandbox `https://api.truelayer-sandbox.com/`, live `https://api.truelayer.com/`. Source: [Test payments in sandbox](https://docs.truelayer.com/docs/test-payments-in-sandbox). Confirm the Data v3 host on the day of the build. The v3 connection page describes the resource and the token, and the host to use for a first build should be taken from that page's current examples.
9. Account-holder verification sandbox behaviour, including the names that produce a match, a partial match, and a non-match, is on [Account holder verification](https://docs.truelayer.com/docs/account-holder-verification-1). Use a synthetic IBAN from that page's test table. Do not put a real account number in the request.

The quickstart's example scope includes `balance`. Data v3's affordability row does not list `balance` as a separate scope. Follow the scope list for the API version you confirm in the open question above.

## Keys and config

Not added to `.env.example` in this change.

| Name | Where | Notes |
|---|---|---|
| `TRUELAYER_CLIENT_ID` | `.env`, GitHub Actions secret, or the production secrets manager | Sandbox ids start with `sandbox-`. Production must reject a sandbox id ([#143](https://github.com/abelunbound/ajocredit/issues/143)) |
| `TRUELAYER_CLIENT_SECRET` | same | Issued in Console. Never committed, never logged |
| `TRUELAYER_REDIRECT_URI` | config | Must match Console character for character |
| `TRUELAYER_AUTH_URL` | config | `https://auth.truelayer.com/` in the quickstart |
| `TRUELAYER_API_BASE` | config | Sandbox or live host, once confirmed for Data v3 |
| `TRUELAYER_TOKEN_ENCRYPTION_KEY` | secret, outside the database | Encrypts the member access token at rest ([#43](https://github.com/abelunbound/ajocredit/issues/43)) |

CI does not call TrueLayer. A future sandbox test stores the secret in GitHub Actions secrets. Live keys follow [#145](https://github.com/abelunbound/ajocredit/issues/145).

The member access token is not one of these environment variables. It is per member and encrypted in the database.

## Risks and open questions

- [#65](https://github.com/abelunbound/ajocredit/issues/65) blocks real users until the data protection impact assessment covers Open Banking data. Bank transactions are personal data. The design stores the band and reasons, not the feed. Retention of the band is part of that assessment.
- A stolen token is a stolen view of the member's bank (threat T-21). Encryption, least scope, and one-time access are the controls already in the threat model.
- Data v1 and Data v3 are both documented. Building the wrong one wastes the sandbox test. Confirm before [#43](https://github.com/abelunbound/ajocredit/issues/43).
- `one_time` duration depends on the bank. The page does not give a single number of days.
- Verification is public beta and needs TrueLayer to enable the `client_id`.
- The verify response can include the account number and sort code. Those must not be written to the audit log or returned to other members.
- Name match will fail on joint accounts or on a name the bank abbreviates. The Verification API returns `match_score` and can list several holders. What score allows a join is an open product question. A failed match is not, by itself, an affordability decline.
- TrueLayer Payments is a separate product. It is out of scope while Modulr is the payment partner.
- Sandbox client secrets are still secrets. Mock Bank's published test username and password are fictitious and are the exception documented by TrueLayer.

## Tickets

| Ticket | How this document maps |
|---|---|
| [#43](https://github.com/abelunbound/ajocredit/issues/43) | Dummy, then sandbox, connection. Tokens encrypted |
| [#52](https://github.com/abelunbound/ajocredit/issues/52) | Transactions are an input to the band, then discarded. See [affordability.md](affordability.md) |
| [#50](https://github.com/abelunbound/ajocredit/issues/50) | Name match, and the same bank seen on two users |
| [#53](https://github.com/abelunbound/ajocredit/issues/53) | Optional account-holder verification of a new payout destination |
| [#65](https://github.com/abelunbound/ajocredit/issues/65) | DPIA gate before real Open Banking data |
| [#143](https://github.com/abelunbound/ajocredit/issues/143), [#145](https://github.com/abelunbound/ajocredit/issues/145) | Live credentials and redirect URIs |

## Sources

- [Quickstart: Create a Console account](https://docs.truelayer.com/docs/quickstart-create-a-console-account)
- [Quickstart: Retrieve test bank data](https://docs.truelayer.com/docs/quickstart-retrieve-bank-data)
- [General Data API concepts](https://docs.truelayer.com/docs/general-data-api-concepts)
- [Data API v1 overview](https://docs.truelayer.com/docs/data-api-basics)
- [Enable your users to connect their bank account](https://docs.truelayer.com/docs/enable-your-users-to-connect-their-bank-account)
- [Create a connection (Data v3)](https://docs.truelayer.com/docs/create-a-connection-v3)
- [Verification API basics](https://docs.truelayer.com/docs/verification-api-basics)
- [Verify an account](https://docs.truelayer.com/docs/verify-an-account)
- [Account holder verification](https://docs.truelayer.com/docs/account-holder-verification-1)
- [Test payments in sandbox](https://docs.truelayer.com/docs/test-payments-in-sandbox)
