# WhatsApp order updates: setup guide

Students who tick "Send my order updates on WhatsApp" get three messages:

1. **Order confirmed** when their payment goes through.
2. **Order ready** when the restaurant marks it ready.
3. **Order cancelled** when the *restaurant* cancels it (they are told the money is now store credit).

Nothing is sent until you finish this guide and set `WHATSAPP_ENABLED=true`. Until then the app behaves exactly as before.

## Roll-out order (important)

1. **Run the database migration first** (`python -m alembic upgrade head`, pointed at your live database). It only *adds* things, so the currently running code is not affected.
2. **Then** deploy the new backend. (The other way round, every login fails until the migration runs.)
3. Add the settings below to **both** backend deployments (the two Vercel projects that share the database).
4. Test with `WHATSAPP_TEST_ALLOWLIST` set to your own number (see "Testing safely").
5. When happy, empty `WHATSAPP_TEST_ALLOWLIST` to go live for everyone who opted in.

## 1. Meta account

You need a Meta (Facebook) Business account. In <https://developers.facebook.com>:

1. **Create app** -> type **Business** -> add the **WhatsApp** product. This creates a *WhatsApp Business Account*.
2. **API Setup** -> add a **phone number**. It must be a number that is **not** currently registered in the normal WhatsApp or WhatsApp Business *app* (use a fresh SIM, or delete the number from the app first). Customers will see messages from it, so use one you are happy to show.
3. Meta may ask you to complete **Business Verification** before you can message beyond a small test group.

For quick testing Meta gives you a free test number that can message up to five phone numbers you add to its list.

## 2. Credentials -> settings

| Setting | Where to find it |
|---|---|
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp -> API Setup -> "Phone number ID" (a long number; *not* the phone number itself) |
| `WHATSAPP_ACCESS_TOKEN` | A **permanent** token: Business Settings -> Users -> **System users** -> add one -> assign your app -> **Generate token** with `whatsapp_business_messaging` and `whatsapp_business_management`. (The token on the API Setup page expires in about a day: fine for a first test, not for production.) |
| `WHATSAPP_APP_SECRET` | App settings -> Basic -> **App secret**. Used to check that delivery reports really come from Meta. |
| `WHATSAPP_VERIFY_TOKEN` | A password **you make up** (e.g. a long random string). You type the same one into Meta when registering the webhook. |
| `WHATSAPP_ENABLED` | `true` to switch it on. |

Optional: `WHATSAPP_LANGUAGE` (default `en`), `WHATSAPP_API_VERSION` (default `v21.0`), `WHATSAPP_DEFAULT_COUNTRY_CODE` (default `91`), `WHATSAPP_TIMEOUT_SECONDS` (default `3.5`), and one template name per message (below). Treat the token and secret like passwords: never commit them or paste them in chat.

## 3. Message templates

WhatsApp only lets a business *start* a conversation with an approved template. In WhatsApp Manager -> **Message templates** -> **Create template**, create these three **exactly** as written (Category **Utility**, Language **English**). Approval usually takes minutes to a couple of days.

**Name:** `order_confirmed`  |  **Category:** Utility  |  **Language:** English

> Hi {{1}}, your Saturdays order {{2}} at {{3}} is confirmed ✅
>
> Pickup: {{4}}
> Total: ₹{{5}}
>
> Show your order code at the counter. We'll message you again when it's ready.

*Example values Meta asks for:* {{1}} = Asha, {{2}} = K7M2, {{3}} = Food Court, {{4}} = today at 1:30 PM, {{5}} = 190

**Name:** `order_ready`  |  **Category:** Utility  |  **Language:** English

> Good news! Your Saturdays order {{1}} at {{2}} is ready 🎉
>
> Show your order code at the counter to collect it.

*Example values Meta asks for:* {{1}} = K7M2, {{2}} = Food Court

**Name:** `order_cancelled`  |  **Category:** Utility  |  **Language:** English

> Hi {{1}}, sorry: {{2}} couldn't make your Saturdays order {{3}}, so it has been cancelled.
>
> What you paid has been added to your Saturdays store credit, ready to use on your next order.

*Example values Meta asks for:* {{1}} = Asha, {{2}} = Food Court, {{3}} = K7M2

If you name a template differently, set `WHATSAPP_TEMPLATE_ORDER_CONFIRMED`, `WHATSAPP_TEMPLATE_ORDER_READY` or `WHATSAPP_TEMPLATE_ORDER_CANCELLED` to match. **Leave one empty to switch that message off.**

If Meta rejects a template, the usual reasons are: the category (keep it Utility, and keep it about a specific order), a variable at the very start or end of the text, or missing example values.

## 4. Webhook (delivery reports and STOP)

WhatsApp -> **Configuration** -> Webhook -> **Edit**:

* **Callback URL:** `https://YOUR-BACKEND/api/v1/notifications/whatsapp/webhook`
* **Verify token:** the value of `WHATSAPP_VERIFY_TOKEN`

Then **subscribe to the `messages` field**. This is how the log learns a message was delivered, read or failed, and how a customer replying **STOP** is switched off. Requests without a valid Meta signature are refused.

## 5. Testing safely

* Locally: `WHATSAPP_PROVIDER=mock` prints what *would* be sent and sends nothing.
* Against real WhatsApp, first set `WHATSAPP_TEST_ALLOWLIST=919876543210` (your number, digits with country code; several separated by commas). **Only** those numbers are ever messaged; every real customer is skipped.
* Place a test order as a student who ticked the box, pay, mark it ready from the restaurant portal, then cancel another. You should receive the three messages.

See what happened to every message:

```sql
SELECT created_at, event, status, error, recipient
FROM notifications WHERE channel = 'WHATSAPP'
ORDER BY created_at DESC LIMIT 20;
```

`status` goes `SENT` -> `DELIVERED` -> `READ`, or `FAILED` with the reason in `error`.

## 6. Good to know

* **Cost.** Meta charges per *delivered* utility message (roughly 12-15 paise in India at the time of writing, plus GST; some providers add a markup). Three messages per order is about 35-45 paise. Check Meta's current rate card.
* **Consent.** Only students who ticked the box (the time is recorded) are messaged, they can untick it in their profile, and replying STOP switches it off.
* **Unpaid orders are never messaged.** Orders exist before payment; a message is sent only once payment has succeeded.
* **A message is sent at most once** per order and event, even if a student retries or Razorpay's webhook also fires.
* **A failed message is not retried automatically** (sending twice is worse than missing one). It stays in the log as `FAILED` with the reason. The common ones: `190` token expired or revoked (make a new one), `131026` the number is not on WhatsApp, `132000`/`132001` template name or language does not match an approved template.
* **A slow WhatsApp never delays an order:** it is abandoned after `WHATSAPP_TIMEOUT_SECONDS`.
* **Privacy.** Numbers are stored with the student's profile and in the message log. Make sure your privacy policy says students' numbers are used to send order updates on WhatsApp.
