"""One bounded real local-model attempt; acceptance executes only in Docker."""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from ahos.llm_executor import load_settings, make_model_executor
from ahos.workforce_execution import WorkItem

root=Path(sys.argv[1]).absolute()
root.mkdir(parents=True,exist_ok=False)
project=root/'project';project.mkdir()
source=project/'reservation_math.py'
source.write_text('def available(capacity, used):\n    return capacity + used\n',encoding='utf-8')
contract=project/'test_accept.py'
contract.write_text('''import sys, unittest
sys.path.insert(0,'/work')
from reservation_math import available
class Acceptance(unittest.TestCase):
 def test_subtract(self): self.assertEqual(available(10,3),7)
 def test_exhausted(self): self.assertEqual(available(4,7),0)
 def test_zero(self): self.assertEqual(available(0,0),0)
 def test_equal(self): self.assertEqual(available(12,12),0)
 def test_negative_capacity(self):
  with self.assertRaises(ValueError): available(-1,0)
 def test_negative_used(self):
  with self.assertRaises(ValueError): available(1,-1)
if __name__=='__main__': unittest.main()
''',encoding='utf-8')
contract_hash=hashlib.sha256(contract.read_bytes()).hexdigest()
docker=shutil.which('docker') or 'C:/Program Files/Docker/Docker/resources/bin/docker.exe'
command=[docker,'run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
         '--pids-limit','64','--memory','128m','--cpus','0.5','--user','65534:65534',
         '--mount','type=bind,source='+str(project)+',target=/work,readonly','--workdir','/work',
         'ahos-candidate-tests:local','-I','/work/test_accept.py']
baseline=subprocess.run(command,capture_output=True,text=True,timeout=60)
(root/'baseline.txt').write_text(baseline.stdout+baseline.stderr,encoding='utf-8')
if baseline.returncode!=1 or 'Ran 6 tests' not in baseline.stderr:
    raise RuntimeError('Baseline acceptance container did not run correctly; no model called')
settings=load_settings({'AHOS_LLM_BASE_URL':'http://127.0.0.1:11434/v1','AHOS_LLM_MODEL':'qwen2.5-coder:1.5b'})
item=WorkItem(task_id='free-local:produce',title='Fix reservation_math.py available(capacity, used): for nonnegative numbers return max(0, capacity - used). Raise ValueError when capacity or used is negative. Change only reservation_math.py using find/replace. Do not change tests. Keep risk low and verification empty; trusted tests are provided externally.',department='software',required_capabilities=frozenset({'python'}))
executor=make_model_executor(project,root/'evidence',settings=settings,spend_ledger=root/'costs.jsonl',verify_command=command,run_browser_check=False)
started=time.monotonic()
result=executor(item,'local-qwen-coder')
assert hashlib.sha256(contract.read_bytes()).hexdigest()==contract_hash
report=dict(status='MODEL_CANDIDATE_ACCEPTED' if result.success else 'MODEL_CANDIDATE_FAILED_OR_BLOCKED',summary=result.summary,
            seconds=round(time.monotonic()-started,3),baseline_failed=True,trusted_contract_sha256=contract_hash,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),provider_api_usd=0,
            scope='single isolated Python function; not a general engineering benchmark',production_applied=False)
if result.success:
    verified=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (root/'independent-recheck.txt').write_text(verified.stdout+verified.stderr,encoding='utf-8')
    report['independent_recheck_passed']=verified.returncode==0 and 'Ran 6 tests' in verified.stderr
    assert report['independent_recheck_passed']
(root/'delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True,indent=2))
