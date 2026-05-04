#!/bin/bash
# Kill all GNL processes (retry up to 15 times) and clean database
for i in $(seq 1 15); do
    pkill -9 -f 'Clone-Chrome-profile' 2>/dev/null
    pkill -9 -f '/opt/google/chrome/chrome' 2>/dev/null
    pkill -9 -f 'nllm-aws-asl' 2>/dev/null
    pkill -9 -f 'process_all_records' 2>/dev/null
    pkill -9 -f 'nova_act' 2>/dev/null
    pkill -9 -f 'setup_chrome_user_data_dir' 2>/dev/null
    sleep 1
done
rm -f '/home/nizar/Clone-Chrome-profile/User Data/SingletonLock'
echo "⛔ All processes stopped"

# Clean database
python /home/nizar/workspace/gnl-process/delete_all_records.py
