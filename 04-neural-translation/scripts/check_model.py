"""Check explicitly installed local NLLB research model metadata; never download weights."""
from pathlib import Path
import argparse,json,sys
parser=argparse.ArgumentParser()
parser.add_argument('--dir',required=True,help='Path to pre-downloaded NLLB model, not an online name')
a=parser.parse_args()
path=Path(a.dir)
if not path.is_dir() or not (path/'config.json').exists():
 sys.exit('Missing model/config.json; no network download will occur')
d=json.loads((path/'config.json').read_text())
print(json.dumps({'directory':str(path.resolve()),'architecture':d.get('architectures'),
                  'model_type':d.get('model_type'),'local_config_verified':True,
                  'license':'VERIFY checkpoint license; NLLB-200 is often CC BY-NC 4.0; research only',
                  'inference_not_proven':True},indent=2))
