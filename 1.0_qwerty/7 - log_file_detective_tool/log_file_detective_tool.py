import os 

def create_fake_log_file():

    # generate a sample log file with some normal activities and a Brute Force Attack simulation
    # format : [TIMESTAMP] IP_ADDRESS - STATUS - MESSAGE

    log_data = [

        "[10:00:01] 192.168.1.50 - SUCCESS - User logged in",
        "[10:00:15] 10.0.0.12 - FAILED - Invalid password attempt",
        "[10:00:16] 10.0.0.12 - FAILED - Invalid password attempt",
        "[10:00:17] 10.0.0.12 - FAILED - Invalid password attempt",
        "[10:00:18] 10.0.0.12 - FAILED - Invalid password attempt",
        "[10:00:19] 10.0.0.12 - FAILED - Invalid password attempt",
        "[10:01:22] 192.168.1.75 - SUCCESS - File downloaded",
        "[10:02:40] 172.16.0.5 - FAILED - Invalid password attempt",
        "[10:03:01] 10.0.0.12 - SUCCESS - User logged in (After 5 failures)",
        "[10:04:10] 192.168.1.50 - SUCCESS - User logged out"

    ]

    with open ("server_logs.txt", "w", encoding="utf-8") as file:
        for line in log_data:
         file.write(line + "\n")

    print("System: Temporary 'server_logs.txt' generated for testing.")

def analyze_logs(file_path, alert_threshold):
   if not os.path.exists(file_path):
      print(f"Error : {file_path} not found!")
      return

   # dictionary to keep track of failed attempts per IP address
   # key: IP Address, Value: Count of failures

   failed_attempts = {}
   
   print(f"\n--- Scanning Log File: {file_path} ---")

 
   with open (file_path, "r" , encoding="utf-8") as file:
      
      for line in file :
         
         # check if the log line indicates a failed login attempt 

         if "FAILED" in line:

            # example line : "[10:00:15] 10.0.0.12 - FAILED - Invalid password attempt"
            # splitting by space to extract the IP address (which is at index 1)

            parts = line.split(" ")
            ip_address = parts[1]

            # increment the failure counter for this IP

            if ip_address in failed_attempts:
               failed_attempts[ip_address] += 1
            else: 
               failed_attempts[ip_address] = 1


    # analysis and reporting 

   print("\n--- Security Alert Report ---")
   suspicious_activity_found = False

   for ip, count in failed_attempts.items():
      
      if count >= alert_threshold:
         print(f"[ALERT] Suspicious IP Detected : {ip}")
         print(f" Reason: {count} failed login attempts (Threshold: {alert_threshold})")
         print(f"Status: Recommended to BLOCK this IP immediately.")
         print("-" * 50)
         suspicious_activity_found = True

   if not suspicious_activity_found :
      
      print("Analysis complete : No suspicious brute-force activity detected!.")


# main program execution 


print ("--- Log File Detective Tool ---")

# automatically create a fake log file for testing

create_fake_log_file()

# set a threshold 

threshold = 3

# run

analyze_logs("server_logs.txt", threshold)


         
