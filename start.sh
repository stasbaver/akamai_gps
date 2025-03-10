#!/bin/bash

nohup python3 /data/gps/xml/sbover/SQA/suites/ew/k6_tests/regression_suite/web_app_full_browser/app.py &
nohup /data/gps/xml/sbover/SQA/suites/ew/k6_tests/regression_suite/web_app_full_browser/result_console_watcher.sh & 
