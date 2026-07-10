#!/bin/bash
# End-to-end smoke test for the Ours API.
# Walks two users (Dylan and Eleanor) through the full MVP journey.
# Auth rides in httpOnly cookies; each user gets a curl cookie jar.
#
# NOT idempotent — it registers fixed emails, so reset test data first:
#   psql -d ours_dev -c "TRUNCATE users, events, communities CASCADE;"
API=http://localhost:8000/api
PASS=0; FAIL=0
JARS=$(mktemp -d)

check () { # check <name> <expected_status> <actual_status>
  if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "ok   $1 ($3)";
  else FAIL=$((FAIL+1)); echo "FAIL $1 (expected $2, got $3)"; fi
}

req () { # req <method> <url> <cookie_jar|""> [json] -> sets STATUS and BODY
  local auth=()
  [ -n "$3" ] && auth=(-b "$3" -c "$3")
  if [ -n "${4:-}" ]; then
    RESP=$(curl -s -w "\n%{http_code}" -X "$1" "$2" "${auth[@]}" -H "Content-Type: application/json" -d "$4")
  else
    RESP=$(curl -s -w "\n%{http_code}" -X "$1" "$2" "${auth[@]}")
  fi
  STATUS=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | sed '$d')
}

login_user () { # login_user <email> <password> <jar>
  req POST $API/auth/login "$3" "{\"email\":\"$1\",\"password\":\"$2\"}"
}

json () { echo "$BODY" | /usr/bin/python3 -c "import sys, json; print(json.load(sys.stdin)$1)"; }

echo "=== health ==="
req GET http://localhost:8000/health ""
check "health" 200 "$STATUS"

echo "=== auth ==="
req POST $API/auth/register "" '{"email":"dylan@example.com","password":"dylan-pass-123","display_name":"Dylan"}'
check "register dylan" 201 "$STATUS"
DYLAN_ID=$(json "['id']")
req POST $API/auth/register "" '{"email":"eleanor@example.com","password":"eleanor-pass-123","display_name":"Eleanor"}'
check "register eleanor" 201 "$STATUS"
ELEANOR_ID=$(json "['id']")
req POST $API/auth/register "" '{"email":"dylan@example.com","password":"whatever-123","display_name":"Imposter"}'
check "duplicate email rejected" 400 "$STATUS"
req POST $API/auth/register "" '{"email":"shorty@example.com","password":"short","display_name":"Shorty"}'
check "short password rejected" 422 "$STATUS"

DYLAN="$JARS/dylan"; ELEANOR="$JARS/eleanor"
login_user dylan@example.com dylan-pass-123 "$DYLAN"
check "login dylan (cookie set)" 204 "$STATUS"
login_user eleanor@example.com eleanor-pass-123 "$ELEANOR"
check "login eleanor (cookie set)" 204 "$STATUS"
req POST $API/auth/login "" '{"email":"dylan@example.com","password":"wrong-password"}'
check "bad credentials rejected" 400 "$STATUS"

req GET $API/users/me "$DYLAN"
check "users/me via cookie" 200 "$STATUS"
req GET $API/users/me ""
check "users/me unauthenticated" 401 "$STATUS"

echo "=== profiles & interests ==="
req GET $API/profiles/me "$DYLAN"
check "profiles/me" 200 "$STATUS"
req PATCH $API/profiles/me "$DYLAN" '{"bio":"New to the neighborhood, love shared experiences."}'
check "patch profile" 200 "$STATUS"
req GET $API/interests ""
check "list interests" 200 "$STATUS"
INTEREST_ID=$(json "[0]['id']")
req PUT $API/profiles/me/interests "$DYLAN" "{\"interest_ids\":[\"$INTEREST_ID\"]}"
check "set interests" 200 "$STATUS"
req GET $API/profiles/me/interests "$DYLAN"
check "get my interests" 200 "$STATUS"
GOT_COUNT=$(echo "$BODY" | /usr/bin/python3 -c "import sys, json; print(len(json.load(sys.stdin)['interest_ids']))")
echo "     -> stored interests: $GOT_COUNT (expect 1)"
req GET $API/profiles/$ELEANOR_ID "$DYLAN"
check "public profile" 200 "$STATUS"
req GET "$API/profiles?q=elea" "$DYLAN"
check "search people" 200 "$STATUS"
FOUND_NAME=$(echo "$BODY" | /usr/bin/python3 -c "import sys, json; r=json.load(sys.stdin); print(r[0]['display_name'] if r else 'NOBODY')")
echo "     -> search 'elea' found: $FOUND_NAME (expect Eleanor)"
req GET "$API/profiles?q=e" "$DYLAN"
check "search query too short -> 422" 422 "$STATUS"

echo "=== events (Sunset Park, Brooklyn) ==="
req POST $API/events "$DYLAN" "{\"kind\":\"gathering\",\"title\":\"Board games in the park\",\"description\":\"Casual games, all welcome\",\"location\":{\"lat\":40.6552,\"lng\":-74.0069},\"address\":\"41st St park entrance\",\"starts_at\":\"2026-08-01T15:00:00Z\",\"visibility\":\"public\",\"capacity\":2,\"interest_ids\":[\"$INTEREST_ID\"]}"
check "create event" 201 "$STATUS"
EVENT_ID=$(json "['id']")
req POST $API/events "$ELEANOR" '{"kind":"help_request","title":"Help moving a bookshelf","location":{"lat":40.6560,"lng":-74.0080},"starts_at":"2026-08-02T10:00:00Z","visibility":"public"}'
check "create help request" 201 "$STATUS"
HELP_ID=$(json "['id']")
req POST $API/events "$ELEANOR" '{"kind":"gathering","title":"Family only dinner","location":{"lat":40.6560,"lng":-74.0080},"starts_at":"2026-08-03T18:00:00Z","visibility":"private"}'
check "create private event" 201 "$STATUS"
PRIVATE_ID=$(json "['id']")

req GET "$API/events?lat=40.6552&lng=-74.0069&radius_m=3000" "$DYLAN"
check "map discovery" 200 "$STATUS"
FOUND=$(echo "$BODY" | /usr/bin/python3 -c "import sys, json; print(len(json.load(sys.stdin)))")
echo "     -> events visible to dylan nearby: $FOUND (expect 2: private one hidden)"
req GET "$API/events?lat=40.7580&lng=-73.9855&radius_m=1000" "$DYLAN"
NEAR_TSQ=$(echo "$BODY" | /usr/bin/python3 -c "import sys, json; print(len(json.load(sys.stdin)))")
echo "     -> events near Times Square (12km away): $NEAR_TSQ (expect 0)"
req GET "$API/events/$PRIVATE_ID" "$DYLAN"
check "private event hidden from stranger" 404 "$STATUS"
req GET "$API/events/$EVENT_ID" "$ELEANOR"
check "event detail" 200 "$STATUS"
ADDR=$(json "['address']")
echo "     -> address for non-participant: $ADDR (expect None)"

echo "=== rsvp & capacity ==="
req PUT $API/events/$EVENT_ID/rsvp "$ELEANOR" '{"status":"going"}'
check "eleanor rsvp going" 200 "$STATUS"
req GET "$API/events/$EVENT_ID" "$ELEANOR"
ADDR=$(json "['address']")
echo "     -> address after going: $ADDR (expect street address)"
req POST $API/auth/register "" '{"email":"mitch@example.com","password":"mitch-pass-123","display_name":"Mitch"}'
MITCH_ID=$(json "['id']")
MITCH="$JARS/mitch"
login_user mitch@example.com mitch-pass-123 "$MITCH"
req PUT $API/events/$EVENT_ID/rsvp "$MITCH" '{"status":"going"}'
check "mitch rsvp going" 200 "$STATUS"
req POST $API/auth/register "" '{"email":"bob@example.com","password":"bob-pass-1234","display_name":"Bob"}'
BOB_ID=$(json "['id']")
BOB="$JARS/bob"
login_user bob@example.com bob-pass-1234 "$BOB"
req PUT $API/events/$EVENT_ID/rsvp "$BOB" '{"status":"going"}'
check "capacity full -> 409" 409 "$STATUS"
req GET $API/events/$EVENT_ID/participants "$DYLAN"
check "list participants" 200 "$STATUS"

echo "=== connections & invites ==="
req POST $API/connections "$DYLAN" "{\"addressee_id\":\"$ELEANOR_ID\"}"
check "request connection" 201 "$STATUS"
CONN_ID=$(json "['id']")
req POST $API/connections "$ELEANOR" "{\"addressee_id\":\"$DYLAN_ID\"}"
check "reverse duplicate -> 409" 409 "$STATUS"
req PATCH $API/connections/$CONN_ID "$DYLAN" '{"status":"accepted"}'
check "requester cannot accept -> 403" 403 "$STATUS"
req PATCH $API/connections/$CONN_ID "$ELEANOR" '{"status":"accepted"}'
check "addressee accepts" 200 "$STATUS"
req GET $API/connections "$DYLAN"
check "list connections" 200 "$STATUS"
req POST $API/events/$PRIVATE_ID/invites "$ELEANOR" "{\"user_id\":\"$DYLAN_ID\"}"
check "invite connection to private event" 201 "$STATUS"
req POST $API/events/$PRIVATE_ID/invites "$ELEANOR" "{\"user_id\":\"$MITCH_ID\"}"
check "invite non-connection -> 403" 403 "$STATUS"
req GET "$API/events/$PRIVATE_ID" "$DYLAN"
check "invited user can now see private event" 200 "$STATUS"
req PUT $API/events/$PRIVATE_ID/rsvp "$DYLAN" '{"status":"going"}'
check "accept invite via rsvp" 200 "$STATUS"

echo "=== messages ==="
req POST $API/events/$EVENT_ID/messages "$ELEANOR" '{"body":"Should I bring my own chair?"}'
check "participant posts message" 201 "$STATUS"
req GET $API/events/$EVENT_ID/messages "$DYLAN"
check "host reads messages" 200 "$STATUS"
req POST $API/events/$EVENT_ID/messages "$BOB" '{"body":"I never joined but hello"}'
check "non-participant message -> 403" 403 "$STATUS"

echo "=== blocks & reports ==="
req POST $API/blocks "$ELEANOR" "{\"blocked_id\":\"$BOB_ID\"}"
check "block user" 201 "$STATUS"
req POST $API/connections "$BOB" "{\"addressee_id\":\"$ELEANOR_ID\"}"
check "blocked user cannot connect -> 403" 403 "$STATUS"
req GET "$API/profiles?q=Eleanor" "$BOB"
BLOCKED_SEARCH=$(echo "$BODY" | /usr/bin/python3 -c "import sys, json; print(len(json.load(sys.stdin)))")
echo "     -> blocked user searching Eleanor finds: $BLOCKED_SEARCH (expect 0)"
req GET $API/blocks "$ELEANOR"
check "list blocks" 200 "$STATUS"
req POST $API/reports "$ELEANOR" "{\"reported_user_id\":\"$BOB_ID\",\"reason\":\"spam\",\"details\":\"unwanted messages\"}"
check "file report" 201 "$STATUS"
req POST $API/reports "$ELEANOR" '{"reason":"no target"}'
check "report without target -> 422" 422 "$STATUS"

echo "=== cleanup-ish checks ==="
req DELETE $API/events/$HELP_ID/rsvp "$DYLAN"
check "withdraw nonexistent rsvp -> 404" 404 "$STATUS"
req DELETE $API/events/$HELP_ID "$DYLAN"
check "non-host delete -> 403" 403 "$STATUS"
req DELETE $API/events/$HELP_ID "$ELEANOR"
check "host deletes event" 204 "$STATUS"
req POST $API/auth/logout "$DYLAN"
check "logout" 204 "$STATUS"
req GET $API/users/me "$DYLAN"
check "cookie cleared after logout -> 401" 401 "$STATUS"
req DELETE $API/users/me "$BOB"
check "delete account" 204 "$STATUS"
req POST $API/auth/login "" '{"email":"bob@example.com","password":"bob-pass-1234"}'
check "deleted user cannot log in" 400 "$STATUS"

rm -rf "$JARS"
echo
echo "RESULT: $PASS passed, $FAIL failed"
exit $FAIL
