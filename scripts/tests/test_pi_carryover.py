import os
import subprocess
import pytest
import uuid
import time
import tempfile
import json
import shutil

@pytest.fixture
def herdr_socket():
    socket_path = f"/tmp/herdr-test-{uuid.uuid4().hex}.sock"
    temp_home = tempfile.mkdtemp(prefix="herdr-test-home-")
    
    os.environ["HERDR_SOCKET"] = socket_path
    os.environ["XDG_CONFIG_HOME"] = os.path.join(temp_home, ".config")
    os.environ["XDG_DATA_HOME"] = os.path.join(temp_home, ".local", "share")
    os.environ["XDG_STATE_HOME"] = os.path.join(temp_home, ".local", "state")
    
    herdr_bin = shutil.which("herdr") or "/usr/local/bin/herdr"
    proc = subprocess.Popen([herdr_bin, "server", "--headless"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(1) 
    
    yield socket_path
    
    proc.terminate()
    proc.wait()
    if os.path.exists(socket_path):
        os.remove(socket_path)
        
    shutil.rmtree(temp_home, ignore_errors=True)

def test_shell_injection_rejection(herdr_socket):
    env = os.environ.copy()
    env["HERDR_SOCKET"] = herdr_socket
    
    result = subprocess.run(
        ["bash", "scripts/bin/pi-carryover-loader.sh", "invalid; echo 'hacked'", "tab1", "sess1", "agent1"],
        env=env,
        capture_output=True,
        text=True
    )
    assert result.returncode == 1
    assert "Invalid PANE_ID" in result.stdout
    assert "hacked" not in result.stdout

def test_carryover_bridge_e2e(herdr_socket):
    env = os.environ.copy()
    env["HERDR_SOCKET"] = herdr_socket
    env["HERDR_PANE_ID"] = "pane1"
    env["HERDR_TAB_ID"] = "tab1"
    env["PI_SESSION_ID"] = "sess1"
    env["PI_AGENT_ID"] = "agent1"
    
    pi_bin = shutil.which("pi") or "/usr/local/bin/pi"
    subprocess.run(
        [pi_bin, "-e", ".pi/extensions/carryover-bridge.ts", "--print", "trigger carryover"],
        env=env,
        capture_output=True,
        text=True
    )
    
    time.sleep(1)
    
    handoff_dir = ".pi/handoff/sess1/agent1"
    assert os.path.exists(handoff_dir)
    assert os.path.exists(os.path.join(handoff_dir, "journal.json"))

def test_tab_renamed_successfully(herdr_socket):
    env = os.environ.copy()
    env["HERDR_SOCKET"] = herdr_socket
    
    herdr_bin = shutil.which("herdr") or "/usr/local/bin/herdr"
    workspace = subprocess.run(
        [herdr_bin, "workspace", "create"],
        env=env,
        capture_output=True,
        text=True
    ).stdout.strip()
    
    ws_data = json.loads(workspace)
    tab_id = ws_data["result"]["workspace"]["active_tab_id"]
    pane_id = ws_data["result"]["root_pane"]["pane_id"]

    result = subprocess.run(
        ["python3", "scripts/bin/pi-carryover-rotate.py", pane_id, tab_id, "sess1", "agent1"],
        env=env,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0

def test_seal_command_execution(herdr_socket):
    env = os.environ.copy()
    env["HERDR_SOCKET"] = herdr_socket
    
    herdr_bin = shutil.which("herdr") or "/usr/local/bin/herdr"
    workspace = subprocess.run(
        [herdr_bin, "workspace", "create"],
        env=env,
        capture_output=True,
        text=True
    ).stdout.strip()
    
    ws_data = json.loads(workspace)
    tab_id = ws_data["result"]["workspace"]["active_tab_id"]
    pane_id = ws_data["result"]["root_pane"]["pane_id"]

    result = subprocess.run(
        ["bash", "scripts/bin/pi-carryover-seal.sh", pane_id, tab_id, "sess2", "agent2"],
        env=env,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    
    handoff_dir = ".pi/handoff/sess2/agent2"
    assert os.path.exists(handoff_dir)
    
    with open(os.path.join(handoff_dir, "dispatch.json"), "r") as f:
        data = json.load(f)
        assert data.get("status") == "sealed"

def test_rotate_with_carryover_path(herdr_socket):
    env = os.environ.copy()
    env["HERDR_SOCKET"] = herdr_socket
    
    herdr_bin = shutil.which("herdr") or "/usr/local/bin/herdr"
    workspace = subprocess.run(
        [herdr_bin, "workspace", "create"],
        env=env,
        capture_output=True,
        text=True
    ).stdout.strip()
    
    ws_data = json.loads(workspace)
    tab_id = ws_data["result"]["workspace"]["active_tab_id"]
    pane_id = ws_data["result"]["root_pane"]["pane_id"]

    session_id = "sess_with_path"
    agent_id = "agent_with_path"
    log_path = f".pi/handoff/{session_id}/{agent_id}/rotate.log"
    
    if os.path.exists(log_path):
        os.remove(log_path)

    result = subprocess.run(
        ["python3", "scripts/bin/pi-carryover-rotate.py", pane_id, tab_id, session_id, agent_id, "my-carryover-file.md"],
        env=env,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert os.path.exists(log_path), "rotate.log was not created"
    
    with open(log_path, "r") as f:
        log_content = f.read()
        
    for line in log_content.strip().split('\n'):
        if not line.strip(): continue
        try:
            data = json.loads(line)
            assert "error" not in data, f"Herdr command failed: {data['error']}"
        except json.JSONDecodeError:
            pass
