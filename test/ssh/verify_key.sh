#!/bin/sh

curl -s -G --data-urlencode "pubkey=$1 $2" -H "x-api-key:helloworld" http://janus-sync-janus-sync-1:8085/ssh/validate
