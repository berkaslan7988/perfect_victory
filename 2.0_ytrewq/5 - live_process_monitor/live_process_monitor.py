import psutil

def list_active_processes():
    print(f"\n{'PID': <8} | {'Process Name': <30} | {'Memory Usage (MB)': <15}")
    print("-" * 60)

    process_count = 0

    # psutil.process_iter() loops through all running processes on the OS
    # we request 'pid', 'name' and 'memory_info' attributes for efficiency
     
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            # extract the process details into a dictionary
            
            proc_info = proc.info

            pid = proc_info['pid']
            name = proc_info['name']

            # get the memory usage in bytes and convert it to Megabytes 
            # RSS (Resident Set Size) represents the actual RAM allocated for the process
            
            memory_bytes = proc_info['memory_info'].rss
            memory_mb = memory_bytes / (1024 * 1024)

            # print the process details in a clean , formatted table
            
            print(f"{pid:<8} | {name:<30} | {memory_mb:<15.2f}")
            process_count += 1

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # system processes or protected antivirus processes might deny access
            # we skip them to prevent the tool from crashing 
            pass

    print("-" * 60)
    print(f"[SUCCESS] Scan Complete. Total Active Processes Monitored : {process_count}")

# main program execution

print("--- Live Process Monitor ---")
print("Scanning the operating system kernel for active processes...\n")

input("Press Enter to fetch the current system process map...")
list_active_processes()