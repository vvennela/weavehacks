# Local controller recovery

This recovers the connection between a running Sera optimizer in Molab and its
local Codex controller. It does not restart or resume a stopped GPU optimizer.

## What now happens automatically

- A failed connection or read no longer stops after three attempts. The controller
  retries within its existing idle deadline. Each group of three reads uses 1- and
  2-second waits. Further groups wait 1, 2, 4, then at most 5 seconds.
- Each remote command has a timeout of at most 60 seconds, shortened to the
  remaining deadline. A poll that reaches the idle deadline stops cleanly. Failure
  to establish the initial connection before that deadline remains an error.
- Before sending a response, the controller saves `delivery.json` and reads the
  remote response status. A matching response needs no second write. A different
  response stops the controller without overwriting evidence.
- If sending succeeds but its acknowledgement is lost, the controller reads the
  status again. It sends again only when no response exists. The remote publisher
  still uses an atomic, non-overwriting write.
- Request expiry still applies. No new LM call or response write is permitted
  after expiry. Following an ambiguous write, up to five seconds of final
  read-only reconciliation can confirm an already saved response. This grace also
  stays within the controller idle deadline. Expired work does not stop live peers.

The idle setting is not a total experiment or trial limit. Active requests still
have their original expiry. Three LM calls can run in parallel; recovery does not
add GPU trials or reissue the same LM request.

## Safe controller restart

Run the same controller command with the same relay and local output directories.
Do not delete or rename its request directories.

1. If a saved delivery exists, its request identity and response shape are checked
   before the response is reused.
2. Otherwise, a saved successful CLI result can be rebuilt from its original final
   text and completed CLI events. The exact saved request must match. New calls
   also save the process exit status before accepting recovered output.
3. An incomplete old attempt is not run again. It returns a safe controller error.
   Sera's existing provider retry policy can then make a distinct new request.
4. Malformed delivery records and conflicting remote responses fail closed.

A local file lock prevents two controllers from using the same output directory
at once. Use one controller per relay. Controllers on different computers, or with
different output directories, are not protected by this local lock. Keep the same
local directory when restarting. `--max-requests` counts work in the current
controller process, not lifetime work across restarts; `none` remains uncapped.

The controller does not launch itself again after being killed. A hard kill can
leave a child CLI process alive; restart never launches a duplicate for its request
ID. Full process supervision and remote request leases are not implemented.

## Upgrade order

1. Install the updated Sera source in Molab first. Its `sera.relay` module must
   expose `response_status` alongside `pending_requests` and `publish_response`.
2. Start the updated local controller against that source, with the existing
   pairing token supplied through the environment. Do not put tokens in commands
   saved to Git or in a report.
3. Keep both request and response records. The reconciliation operation is
   read-only; it needs those records to distinguish a missing response from a
   matching or conflicting one.

Do not change the Molab notebook kernel or GPU process merely to recover this
connection. A deleted Molab server, lost GPU process, missing relay files, expired
credentials, or destroyed local output directory cannot be repaired by retries.

## Recovery evidence and tests

The local output directory contains append-only `recovery.jsonl`. Each record has
an event name, timestamp, retry count, and optional request ID. Events include
`transport-retry`, `transport-recovered`, `recovery-deadline`,
`controller-idle-stop`, `request-expired`, and `response-delivered`. These records
contain no exception text, prompt, response, command, URL, or credential. The
existing per-request evidence files still contain prompts and model outputs.

Tests simulate more than three connection failures, recovery, missing and lost
acknowledgements, request expiry, final idle-poll timeout, controller restart,
incomplete or corrupt files, conflicting remote responses, and duplicate local
controllers. They verify no duplicate LM call or response overwrite. These are
local fault-injection tests, not a live network outage measurement.

SQLite-backed optimization resume, replay of interrupted GPU trials, and recovery
after the notebook process dies remain open. This work does not complete those
parts of the product specification.
