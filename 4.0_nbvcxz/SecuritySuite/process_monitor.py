import sys
import time
import os
import psutil

def list_active_processes():
    # Print the clean layout table headers for the UI display
    print(f"\n{'PID': <8} | {'Process Name': <30} | {'Memory Usage (MB)': <15}\n", flush=True)
    print("-" * 60 + "\n", flush=True)

    process_count = 0

    # psutil.process_iter() loops through all running processes on the OS
    # We request 'pid', 'name' and 'memory_info' attributes for high efficiency
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            # Extract the process details into a safe data dictionary
            proc_info = proc.info
            if not proc_info:
                continue

            pid = proc_info['pid']
            name = proc_info['name']

            # Get the memory usage in bytes and convert it to Megabytes 
            # RSS (Resident Set Size) represents the actual RAM allocated for the process
            memory_bytes = proc_info['memory_info'].rss if proc_info['memory_info'] else 0
            memory_mb = memory_bytes / (1024 * 1024)

            # Print the process details in a clean, formatted table line
            print(f"{pid:<8} | {name:<30} | {memory_mb:<15.2f}\n", flush=True)
            process_count += 1

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # System tasks or protected antivirus processes might deny access
            # We skip them silently to prevent the diagnostic tool from crashing 
            pass

        except Exception as single_proc_error:
            # Catch and log any abnormal pipeline behaviors
            print(f"[!] Error on single process: {single_proc_error}\n", flush=True)

    print("-" * 60 + "\n", flush=True)
    print(f"[SUCCESS] Scan Complete. Total Active Processes Monitored : {process_count}\n", flush=True)

# --- MAIN PROGRAM EXECUTION ---

print("--- Live Process Monitor ---")
print("Scanning the operating system kernel for active processes...\n", flush=True)

# The user-triggered checkpoint prompt
input("Press Enter to fetch the current system process map...\n")

# Fire up the scanner routine
list_active_processes()