# Deployment proof — Telegram & WhatsApp webhook setup (local)

Summary
-------
This document records the status and evidence for the first three setup steps you asked to verify:

1. Gather credentials and confirm deployment mode — *status: partial / pending* (see notes)
2. Configure environment (local) — *status: partial / pending*
3. Start local webhook server and expose with ngrok — *status: attempted / partial*

Notes
-----
- You confirmed your WhatsApp number: `whatsapp:+254758577236`.
- The Telegram bot token was present in an earlier interactive session; it is not set in the current shell used to generate these proofs. Set `TELEGRAM_TOKEN` in the environment in the shell where we run the webhook registration tomorrow.
- Twilio credentials (Account SID + Auth Token) were not set in the environment; provide them tomorrow or set them in the shell if you want me to finish steps 4–6.

Evidence collected (files in `proofs/`)
---------------------------------------
- `proofs/webhook_server.log` — result of health check against the local Flask server (should show `{"status": "ok"}` once server is reachable).
- `proofs/ngrok_install.log` — output from running the local `ngrok` binary; shows that `ngrok` is present but requires a verified account / authtoken to create a public tunnel.
- `proofs/netstat_5000.log` — netstat check showing port 5000 listener (Flask server listening locally).
- `proofs/app_stdout.log` / `proofs/app_stderr.log` — stdout/stderr captures from attempting to run `app.py` (empty if no additional logs were emitted).
- `proofs/credential_proof.txt` — a short note indicating presence or absence of credentials in this shell (no full secrets are stored).

What I did (actions performed)
------------------------------
- Created `proofs/` and collected the above files by running local checks:
  - Attempted to start `app.py` and capture stdout/stderr.
  - Verified Flask `/health` endpoint and wrote result to `proofs/webhook_server.log`.
  - Verified port 5000 is listening and saved the netstat output.
  - Attempted to run `ngrok` and captured the output complaining about missing authtoken in `proofs/ngrok_install.log`.
- Updated `.gitignore` earlier to avoid committing `ngrok/` and `ngrok.zip` binaries.
- Do NOT commit or record any secrets in this repository.

Next steps (you said you'd do this tomorrow)
-------------------------------------------
- Provide or set locally: `NGROK_AUTHTOKEN`, `TWILIO_ACCOUNT_SID`, and `TWILIO_AUTH_TOKEN` in the same shell we use for registration.
- I will then:
  - Install ngrok authtoken and run `ngrok http 5000` to create a public HTTPS URL.
  - Register Telegram `setWebhook` to `https://<public>/webhook/telegram`.
  - Register Twilio WhatsApp webhook to `https://<public>/webhook/whatsapp` and verify messages.
  - Run verification tests (send messages from Telegram & WhatsApp) and capture logs.
  - Clean up local secrets on request.

If you'd like, I can also prepare a short `scripts/register_webhooks.ps1` helper script that will run the setWebhook and Twilio API calls once your tokens are set.

---

Files created: `proofs/*` (logs) and this `DEPLOYMENT_PROOF.md`.

If you want any additional evidence (screenshots, a short recorded terminal transcript, or a helper script), tell me which and I'll add it before you finish tomorrow.
