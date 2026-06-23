import os 
import base64   

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet

def generate_key(master_password, salt):

    # derive a secure cryptographic key from the master password using PBKDF2

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )

    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
    return Fernet(key)

def save_password(cipher_suite, account, password):

    # encrypt the password string
    
    encrypted_password = cipher_suite.encrypt(password.encode()).decode()

    # append the account name and encrypted password to the vault file 

    with open("vault.txt", "a", encoding="utf-8") as file:
        file.write(f"{account}:{encrypted_password}\n")
    print(f"Success: Password for '{account}' has been encrypted and saved! ")


def view_passwords(cipher_suite):

    if not os.path.exists("vault.txt"):
        print("No passwords saved yet.")
        return
    
    print("\n--- Your Decrypted Passwords ---")
    with open("vault.txt", "r", encoding="utf-8") as file:

        for line in file :

        # split the line into account name and encrypted password

            if ":" in line :

                account, encrypted_password = line.strip().split(":", 1)
                
                try:

                    # decrypt password using the master key

                   decrypted_password = cipher_suite.decrypt(encrypted_password.encode()).decode()
                   print(f"Account : {account} | Password : {decrypted_password}")
                
                except Exception:

                    # triggered if the wrong master password was used to generate the key

                    print(f"Account : {account} | Error : Decryption failed (Wrong Master Password).")             

    print ("-" * 32)


# main program execution

print("--- Personal Password Vault ---")


master_pwd = input("Enter your Master Password to unlock the vault: ")

# load or generate a unique random salt for key derivation

salt_file = "vault_salt.bin"
if os.path.exists(salt_file):
    with open(salt_file, "rb") as f:
        salt = f.read()
else:
    salt = os.urandom(16)
    with open(salt_file, "wb") as f:
        f.write(salt)

cipher = generate_key(master_pwd, salt)


while True : 


    print ("\n1 -> Add a new password ")
    print ("2 -> View saved passwords ")
    print("3 -> Exit ")

    choice = input("Choose an option (1-3): ")


    if choice == "1":

        app_name = input("Enter account/application name (e.g., Netflix): ")

        pwd_to_save = input(f"Enter the password for {app_name}: ")

        save_password(cipher, app_name, pwd_to_save)

    elif choice == "2":

        view_passwords(cipher)

    elif choice == "3":

        print("Exiting vault... Goodbye!")
        break

    else:

        print("Invalid Choice. Please select '1' or '2' or '3'.")
