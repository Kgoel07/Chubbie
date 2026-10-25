# WhatsApp feasibility (researched 2026-10-25)

Meta now documents a WhatsApp Business Platform **Groups API**, but it is not practical access for a typical
student hackathon team. The current eligibility material requires an Official Business Account and historically
required a messaging tier of at least 100,000 business-initiated conversations in a rolling 24-hour period. Group
conversations are invite-based and created/managed through eligible Cloud API business numbers; this is not a
general-purpose bot login that can be dropped into any existing student group.

Official references:

- Meta WhatsApp Business Platform documentation: https://developers.facebook.com/docs/whatsapp/
- Groups management reference: https://developers.facebook.com/documentation/business-messaging/whatsapp/reference/whatsapp-business-phone-number/groups-management-api
- WhatsApp Business Platform overview: https://business.whatsapp.com/products/business-platform

Because this project does not have verified eligibility, a production WhatsApp adapter is intentionally **not**
claimed or shipped. `adapter.py` defines the platform boundary and a local group-event simulator. It does not use
WhatsApp Web, browser automation, QR-session scraping, reverse-engineered libraries, or an unofficial provider.

## What a future official adapter would need

1. A Meta Business Portfolio and WhatsApp Business Account.
2. An eligible Official Business Account and Cloud API business phone number.
3. Groups API access for that account, a permanent system-user token, app secret, phone-number ID, and webhook
   verification secret stored outside source control.
4. A public HTTPS webhook endpoint with signature verification and replay protection.
5. Explicit group invitations/consent, the current Meta policy review, and live tests with approved numbers.

At that point, implement `GroupPlatformAdapter` using only the documented Cloud API endpoints. The deterministic
engine, SQLite repository, cooldowns, votes, and privacy-safe export format can remain unchanged.

## Local simulation

```powershell
python -m whatsapp.adapter hatch --demo --group dorm --actor alex --text Byte
python -m whatsapp.adapter play --demo --group dorm --actor sam
python -m whatsapp.adapter teach --demo --group dorm --actor jo --text "ship it"
```

Every line is labeled `SIMULATED`; no WhatsApp request is made.

