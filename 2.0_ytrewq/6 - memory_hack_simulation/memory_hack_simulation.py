import ctypes

def memory_hack_simulation():

# --- phase 1 : the target "game" ---

    print("--- The Target Game ---")

# we create a raw C-type integer in memory (representing player health)

    player_health = ctypes.c_int(100)

# get the exact physical memory address (pointer) of this variable in RAM

    memory_address = ctypes.addressof(player_health)

    print(f"[Game] Player Health initialized at : {player_health.value}")

# display the memory address in hexadecimal format 

    print(f"[System] Variable stored at RAM address : {hex(memory_address)}")

    input("\nPress 'Enter' to launch the Memory Scanner (Cheat Engine)...")

# --- phase 2 : the "hacker" tool ---

    print(f"\n--- Cheat Engine Simulator ---")
    print(f"[Scanner] Target process selected.")
    print(f"[Scanner] Locked onto memory address : {hex(memory_address)}")

    try:
        new_value = int(input("[Scanner] Enter new health value to inject (e.g., 9999) : "))

# --- the reverse engineering magic ---
# we take the physical memory address and directly overwrite the bytes stored there
# memmove (destination_address, source_data, size_of_data)

        ctypes.memmove(memory_address, ctypes.byref(ctypes.c_int(new_value)), ctypes.sizeof(ctypes.c_int))

        print("[Scanner] Memory successfully overwritten! Bypassing Normal Game Logic...")

    except ValueError:
        print("[Error] Invalid Input. Please enter numbers only.")
        return

# --- phase 3 : back to the game ---

    print("--- Back To The Game ---")

# the game doesn't know we manipulated the RAM, it just reads the variable normally

    print(f"[Game] Player Health is now : {player_health.value}")

# simple anti cheat detection simulation

    if player_health.value > 100:
        print("[Game] SYSTEM WARNING : Impossible health value detected! Anti-Cheat flagged.")
    elif player_health.value < 0:
        print("[Game] Player is invincible (God Mode Active).")

# main program execution

if __name__ == "__main__":
    memory_hack_simulation()

