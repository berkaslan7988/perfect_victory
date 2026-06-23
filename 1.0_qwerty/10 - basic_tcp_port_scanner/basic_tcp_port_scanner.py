import socket 
import time    

def scan_ports(target_host, ports_to_scan):
    print(f"\n--- Starting Scan on Host: {target_host} ---")
    print("Checking for open ports...")

    start_time = time.time()
    open_ports = []

    for port in ports_to_scan:
        # create a socket object 
        # AF_INET specifies IPv4, SOCK_STREAM specifies TCP protocol
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # set a timeout so program doesn't wait forever on a closed port.

        s.settimeout(0.5)

        # attempt to connect to the target IP and port
        # connect_ex returns 0 if the connection was successful (port is open)

        result = s.connect_ex((target_host,port))

        if result == 0:
            print(f"[+] Port {port:5d} : OPEN")
            open_ports.append(port)

        else:
            # optional : uncomment the line below if you want to see closed parts too
            # print(f"[-] Port {port:5d} : CLOSED")
            pass

        # always close the socket connection after trying

        s.close()

    end_time = time.time()
    duration = end_time - start_time

    # print final summary report

    print("\n--- Scan Report ---")
    print(f"Scan finished in : {duration:.2f} seconds")
    
    if open_ports:
        print(f"Open ports found : {open_ports}")
    
    else:
        print("No open ports detected in the scanned range.")

        
# main program execution

print("\n--- Basic TCP Port Scanner ---")

# localhost 

target = "127.0.0.1"

# a list of standard common ports

common_ports = [21, 22, 23, 25, 53, 80, 110, 443, 3389, 8050]

# run

scan_ports(target, common_ports)

