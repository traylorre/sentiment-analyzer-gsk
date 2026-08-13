#!/usr/bin/env python3
import sys
import os
import re
import subprocess
import shutil
import json

def validate_id(val):
    if not re.match(r"^[a-zA-Z0-9_:-]+$", val):
        return False
    return True

def run_rotation(pane_id, tab_id, session_id, agent_id, carryover_path=""):
    if not all(validate_id(x) for x in [pane_id, tab_id, session_id, agent_id]):
        print("Invalid input")
        sys.exit(1)

    import datetime
    handoff_dir = f".pi/handoff/{session_id}/{agent_id}"
    os.makedirs(handoff_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")

    # Touch required files if they don't exist
    for f in ["journal.json", "dispatch.json"]:
        open(os.path.join(handoff_dir, f), 'a').close()
        
    # Write metadata
    with open(os.path.join(handoff_dir, "dispatch.json"), "w") as f:
        json.dump({
            "status": "live", 
            "timestamp": timestamp, 
            "pane_id": pane_id, 
            "tab_id": tab_id,
            "carryover_path": carryover_path
        }, f)
        
    herdr_bin = shutil.which("herdr") or os.path.expanduser("~/.local/share/mise/installs/herdr/0.8.0/herdr")
    if not os.path.exists(herdr_bin):
        herdr_bin = "/usr/local/bin/herdr"

    try:
        with open(os.path.join(handoff_dir, "rotate.log"), "a") as log:
            subprocess.run([herdr_bin, "tab", "rename", tab_id, agent_id], check=False, stdout=log, stderr=log)
            # Add a small delay to ensure terminal is ready
            import time
            time.sleep(0.5)
            # Pass the carryover path to the new session if provided
            if carryover_path:
                msg = f"RESUMING FROM {carryover_path}"
                # We can't easily type the whole message, but we can type /new and then tell the user 
                # or inject a prompt. For now, just trigger /new and resume.
                subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "/", "n", "e", "w", "Enter"], check=False, stdout=log, stderr=log)
                time.sleep(2.0)
                # Instead of a generic "resume", let's be explicitly clear.
                resume_text = f"resume context: {carryover_path} STOP DO NOT EXECUTE TASKS WAIT FOR ME".strip()
                resume_keys = []
                for c in resume_text:
                    if c == " ":
                        resume_keys.append("Space")
                    elif c in ("-", ":", ".", "/", "_"):
                        resume_keys.append(c)
                    elif c.isalnum():
                        resume_keys.append(c)
                    else:
                        # Drop unsupported characters to prevent herdr from crashing
                        pass
                
                cmd = [herdr_bin, "pane", "send-keys", pane_id] + resume_keys + ["Enter"]
                
                # Log exactly what we are sending for debugging
                log.write(f"Sending keys: {resume_keys}\n")
                log.flush()
                
                subprocess.run(cmd, check=False, stdout=log, stderr=log)
            else:
                # If no carryover path, just trigger /new
                subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "/", "n", "e", "w", "Enter"], check=False, stdout=log, stderr=log)
    except Exception as e:
        with open(os.path.join(handoff_dir, "error.log"), "a") as f:
            f.write(f"Failed to run herdr: {e}\n")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        sys.exit(1)
    c_path = sys.argv[5] if len(sys.argv) > 5 else ""
    run_rotation(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], c_path)
