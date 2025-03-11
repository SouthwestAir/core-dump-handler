#!/bin/bash -e

trap 'on_failure' EXIT

start_app() {
  echo "Starting Core Dump Handler"
  python3 main.py /core_dumps
}

on_failure () {
  EXIT_CODE=$?
  if [ "$EXIT_CODE" -ne 0 ]; then
    echo "Looks like your app failed, better go check the logs!"
    echo '( ͡°( ͡° ͜ʖ( ͡° ͜ʖ ͡°)ʖ ͡°) ͡°)'
  fi
}

start_app
