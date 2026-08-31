# Global finance digest

This program selects up to ten unique global finance, economic and market-news articles published in the last 24 hours and emails them to `dakangwj@gmail.com`.

## One-time setup

1. Copy `.env.example` to `.env` and enter the Gmail account used to send the message plus a Google App Password. Gmail requires two-step verification before it offers App Passwords.
2. Preview the current digest without sending it:

   ```sh
   python3 global_finance_digest.py --preview
   ```

3. Send a one-off test message:

   ```sh
   python3 global_finance_digest.py --force
   ```

4. Install the macOS background job:

   ```sh
   cp com.dakangwj.global-finance-digest.plist ~/Library/LaunchAgents/
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dakangwj.global-finance-digest.plist
   ```

The background job wakes every 15 minutes. The program itself sends only once, during 08:00-08:59 London time, and records the completed London date. This handles British Summer Time automatically.

To stop it later:

```sh
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.dakangwj.global-finance-digest.plist
```
