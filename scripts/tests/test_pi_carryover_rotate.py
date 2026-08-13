import sys
import os
import subprocess
from unittest.mock import patch, MagicMock

# Add scripts/bin to path so we can import the script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../bin')))
rotate_script = __import__("pi-carryover-rotate")

@patch("time.sleep")
@patch("subprocess.run")
def test_rotation_sends_safe_keys_and_halts_agent(mock_run, mock_sleep, tmp_path):
    # Setup dummy handoff environment
    session_id = "test_session"
    agent_id = "test_agent"
    handoff_dir = f".pi/handoff/{session_id}/{agent_id}"
    os.makedirs(handoff_dir, exist_ok=True)
    
    # Run the rotation with a dummy path containing an illegal character ('@')
    rotate_script.run_rotation("pane_1", "tab_1", session_id, agent_id, "dummy@path.md")
    
    # 1. Verify the 2.0 second sleep occurred before typing
    mock_sleep.assert_any_call(2.0)
    
    # 2. Verify the keys sent to herdr. 
    # It should strip the '@' and append the STOP command.
    expected_text = "resume context: dummypath.md STOP DO NOT EXECUTE TASKS WAIT FOR ME"
    expected_keys = []
    for c in expected_text:
        if c == " ": expected_keys.append("Space")
        else: expected_keys.append(c)
        
    # Find the send-keys call in the mocked subprocess calls
    send_keys_call = None
    for call in mock_run.call_args_list:
        args = call[0][0]
        if "send-keys" in args and expected_keys[0] in args:
            send_keys_call = args
            break
            
    assert send_keys_call is not None, "Did not find the herdr send-keys command"
    
    # Verify the exact array of keys passed to herdr matches what we expect
    # args looks like: ['/usr/local/bin/herdr', 'pane', 'send-keys', 'pane_1', 'r', 'e', 's', 'u', 'm', 'e', 'Space', ...]
    actual_keys_sent = send_keys_call[4:-1] # slice out the binary, pane args, and trailing 'Enter'
    assert actual_keys_sent == expected_keys, f"Keys sent did not match expected whitelist translation.\nExpected: {expected_keys}\nGot: {actual_keys_sent}"
