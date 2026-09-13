# Sera local frontend

From the repository root, run `python3 web/server.py` and open
http://localhost:8877/. This serves the homepage and the authenticated lab preview.

Sign in with the demo login, shown on the sign-in page and printed at startup:

    demo@serademo.com / clustersss

It is seeded into the database on every start, so it survives a wiped or missing
database. Pass `--no-demo-account` to skip seeding it. For your own account use
**Sign in → Create an account**. Accounts are local to this Mac; no email
is sent. Passwords are salted and hashed with PBKDF2-SHA256.
Sessions use HttpOnly, SameSite cookies and expire after 24 hours. Signing out
revokes the current session. The ignored `.local/accounts.sqlite3` database is
outside the publicly served directory and preserves accounts across restarts.

The lab remains an interactive design preview; authentication does not execute
the optimization backend. Run the server instead of `python -m http.server` to
retain route protection and account endpoints. This server binds only to loopback.
