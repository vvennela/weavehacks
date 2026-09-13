#!/usr/bin/env bash
# Ship the live molab embed to useseraai.com.
#
#   1. deploy the Cloudflare Worker that proxies the molab sandbox
#   2. point the Vercel site at it via SERA_MOLAB_URL
#   3. redeploy the site so the new env var takes effect
#
# Run from anywhere:  ./deploy/molab-worker/ship.sh
#
# READ THIS FIRST. The molab sandbox enforces no authentication: anonymous
# requests already get the notebook and can execute code on the GPU. This Worker
# puts that sandbox on a public URL, so anyone who finds it can run code on your
# GPU until the sandbox expires. That is acceptable for a time-boxed demo and
# not acceptable for anything else. Delete the Worker when you are done:
#
#     npx wrangler delete --name sera-molab
#
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"

echo "==> 1/3  Deploying the Cloudflare Worker"
npx --yes wrangler deploy | tee /tmp/sera-worker-deploy.log

# wrangler prints the live URL; pull it out rather than making you copy it.
WORKER_URL="$(grep -oE 'https://[a-z0-9.-]*sera-molab[a-z0-9.-]*\.workers\.dev' /tmp/sera-worker-deploy.log | head -1)"
if [ -z "$WORKER_URL" ]; then
    echo
    echo "Could not read the Worker URL from the deploy output." >&2
    echo "Find it in the output above, then run:" >&2
    echo "  printf '<worker url>' | npx vercel env add SERA_MOLAB_URL production --force" >&2
    echo "  cd '$ROOT/build/sera' && npx vercel deploy --prod" >&2
    exit 1
fi
echo
echo "Worker live at: $WORKER_URL"

echo
echo "==> 2/3  Pointing the site at it"
cd "$ROOT/build/sera"
# --force overwrites any previous value rather than erroring on a duplicate.
printf '%s' "$WORKER_URL" | npx --yes vercel env add SERA_MOLAB_URL production --force

echo
echo "==> 3/3  Redeploying useseraai.com"
npx --yes vercel deploy --prod

echo
echo "Done. Open https://useseraai.com/notebook and sign in."
echo "The molab tab should now embed the live notebook."
echo
echo "If the frame is blank, check the Worker directly first: $WORKER_URL"
