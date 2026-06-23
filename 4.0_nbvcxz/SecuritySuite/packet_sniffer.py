import sys
import time
from scapy.all import sniff, IP, TCP, Raw

def process_packet(packet):
    # check if the packet has an IP layer
    if packet.haslayer(IP):
        ip_src = packet[IP].src # source IP Address (Who sent it)
        ip_dst = packet[IP].dst # destination IP Address (Who receives it)
        proto = packet[IP].proto # protocol number (TCP, UDP, ICMP etc.)

        # determine the protocol name for readability
        proto_name = "OTHER"
        if proto == 6 : proto_name = "TCP"
        elif proto == 17 : proto_name = "UDP"
        elif proto == 1 : proto_name = "ICMP"

        # print basic packet routing information
        print(f"[{proto_name}] {ip_src} ---> {ip_dst}", flush=True)

        # deep packet inspection (dpi) : go inside the TCP layer if it exists
        if packet.haslayer(TCP):
            # check if the packet contains raw data payload (text, HTTP headers, etc.)
            if packet.haslayer(Raw):
                # extract the raw bytes and decode them into readable string
                payload = packet[Raw].load.decode('utf-8', errors='ignore')

                # look for sensitive keywords that might indicate unencrypted login attempts
                keywords = ["user", "pass", "username", "password", "login"]
                if any(keyword in payload.lower() for keyword in keywords):
                    print("\n" + "!" * 50, flush=True)
                    print(f"[ALERT] Potential Sensitive Data Captured via {proto_name}!", flush=True)
                    print(f"From: {ip_src} to {ip_dst}", flush=True)
                    print(f"Packet Content Snippet: \n{payload.strip()[:300]}", flush=True)
                    print("!" * 50 + "\n", flush=True)

# main program execution
print("---- Professional Network Packet Sniffer ----", flush=True)
print("[*] Initializing Network Interface Listener...", flush=True)
print("[*] Sniffing in live traffic. Press Ctrl+C to stop.", flush=True)
print("-" * 60, flush=True)

# start sniffing the network
# prn=process_packet -> sends every captured packet to our function
# store=False -> Do not keep packets in RAM to avoid memory overflow
sniff(prn=process_packet, store=False)
