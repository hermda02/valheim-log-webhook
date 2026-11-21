#!/usr/bin/env bash
set -euo pipefail

docker exec valheim-log-webhook python -c "import os, json, urllib.request, urllib.error; u=os.environ['DISCORD_WEBHOOK_PLAYERS']; data=json.dumps({'username':'Hugin','content':'[JOIN] test joined the realm.'}).encode(); req=urllib.request.Request(u,data=data,headers={'Content-Type':'application/json','User-Agent':'curl/8.5.0','Accept':'*/*'},method='POST');
try:
 r=urllib.request.urlopen(req,timeout=5); print('status',r.status); print(r.read().decode(errors='replace'))
except urllib.error.HTTPError as e:
 print('status',e.code); print(e.read().decode(errors='replace'))"
