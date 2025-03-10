#!/bin/bash

# Predefined directory and output file
WATCH_DIR="/data/gps/xml/sbover/SQA/suites/ew/k6_tests/regression_suite/regression2.0"
OUTPUT_FILE="/data/gps/xml/sbover/SQA/suites/ew/k6_tests/regression_suite/web_app_full_browser/test_console/test.out"

while true; do
    # Find the most recently updated file that starts with 'http', searching up to 3 levels deep
    latest_file=$(find "$WATCH_DIR" -maxdepth 3 -type f -name 'http*' -printf "%T@ %p\n" 2>/dev/null | sort -nr | awk '{print $2}' | head -n 1)

    if [[ -n "$latest_file" && -f "$latest_file" ]]; then
        #echo "Latest file found: $latest_file"

        # Write the filename, then the last 3 lines, overwriting the output file
        {
            #echo "=== $latest_file ==="
            tail -n 19 "$latest_file"
        } > "$OUTPUT_FILE"

        #echo "Filename and last 3 updated rows saved in $OUTPUT_FILE"
    else
        echo "No matching file found in $WATCH_DIR"
    fi

    # Sleep for a few seconds before checking again
    sleep 1
done

