"""Run local API tests and same-origin frontend/backend checks for each website."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PROJECTS=('01-medicinal-plants','02-crop-yield','03-ride-forecast','04-neural-translation')
FAILED=[]
CHECK_SOURCE = '''from fastapi.testclient import TestClient
from server.app import app
client=TestClient(app)
for uri in ("/", "/assets/app.js", "/assets/styles.css", "/api/health"):
    r=client.get(uri)
    assert r.status_code==200, (uri,r.status_code,r.text[:200])
print("Frontend + backend same-origin smoke check passed")
'''
for project in PROJECTS:
    base=ROOT/project
    for cmd in ([sys.executable,'-m','pytest','-q'],['node','--check','web/assets/app.js'],[sys.executable,'-c',CHECK_SOURCE]):
        print(f'\n{project}: {cmd[0]} {cmd[1]}',flush=True)
        result=subprocess.run(cmd,cwd=base,check=False)
        if result.returncode: FAILED.append((project,' '.join(cmd[:2])))
print('\nFAILED:',FAILED or 'none')
sys.exit(bool(FAILED))
