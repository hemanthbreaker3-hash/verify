# Backend-authoritative verification flow

```mermaid
flowchart TD
    A["User opens frontend verification page"] --> B["Frontend redirects user to shortlink"]
    B --> C["User completes shortlink process"]
    C --> D["Backend receives callback"]
    D --> E["Validate Referer only when enabled"]
    E --> F["Validate browser-tab binding"]
    F --> G["Validate server session and verification token"]
    G --> H{"All required checks pass?"}
    H -->|Yes| I["Mark verification complete"]
    I --> J["Redirect to BPT / Telegram destination"]
    H -->|No| K["Block access"]
    K --> L["Return verification error; do not redirect"]
```

## Enforcement rules

- The frontend is for UI/navigation and supplies tab metadata. It never grants verification or access.
- `/api/verify` is the authorization point. It validates the token, signed browser session, flow expiry, and registered tab identifier before granting access.
- If the selected shortener has `referer_enabled: true`, the backend checks that the callback's `Referer` host matches the configured shortener host. Missing or mismatched referers are rejected.
- If `referer_enabled` is false or absent, referer validation is skipped. Tab, session, token, and expiry checks still apply.
- Any failed required check blocks access and prevents the success redirect.
- Configure a stable, high-entropy `SESSION_SECRET_KEY` in the deployment environment. Do not commit it to source control.

## Important limitations

Browser tab identifiers and Referer headers are supplemental signals, not cryptographic proof that a user stayed in one tab. Authorization relies on the signed server session, a short-lived verification token, and backend-side checks. Test the complete browser → shortener → callback → destination flow with each supported shortener before production use.
