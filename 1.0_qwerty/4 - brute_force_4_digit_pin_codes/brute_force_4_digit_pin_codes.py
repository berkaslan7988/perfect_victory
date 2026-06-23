import time 

def brute_force_pin(target_pin) :
    print("\n--- Starting PIN Brute Force Attack ---")
    print("Simulating hacker attempts...")

    # record the starting time (in seconds)

    start_time = time.time ()

    attempts = 0

    # loop through all possible 4-digit numbers (0 to 9999)

    for guess in range (10000):

        attempts += 1

        # format the number as a 4-digit string with leading zeros (e.g., 5 -> "0005")

        guess_string = f"{guess:04d}"

        # check if the guess matches the target PIN

        if guess_string == target_pin:

            # record the end time when the correct PIN is found

            end_time = time.time()

            # calculate the total elapsed time and convert it to milliseconds

            elapsed_time_ms = (end_time - start_time) * 1000

            return guess_string, attempts, elapsed_time_ms
        
# main program execution

print("Brute Force PIN Simulator")

while True: 
            
    user_pin = input("Enter a secret 4-digit PIN (e.g., 1234): ")

    #validation

    if len(user_pin) == 4 and user_pin.isdigit():
        break
    else:
        print("Invalid input! Please enter exactly 4 digits. ")


# run

found_pin, total_attempts, duration = brute_force_pin(user_pin)


# display

print("\n Attack Results")
print(f"Success! Cracked PIN  : {found_pin}")
print(f"Total Attempts Made : {total_attempts}")
print(f"Time Taken : {duration:.2f} milliseconds")
