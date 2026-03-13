#!/bin/bash
# Wrapper script for cron — runs the agent with proper working directory
cd /app
/usr/local/bin/python main.py
