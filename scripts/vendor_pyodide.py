from pathlib import Path
import hashlib,json,urllib.request,concurrent.futures,shutil
VERSION='0.28.3'
BASE=f'https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/'
LOCK_SHA='f6e6f42f451f42affbbcddb00e8c9a3278dcbf399f57aab9f3f568839a7ff4a6'
def vendor(output,cache):
    output=Path(output);cache=Path(cache);output.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
    def download(name,expected=None):
        path=cache/name
        if not path.exists() or (expected and hashlib.sha256(path.read_bytes()).hexdigest()!=expected):
            with urllib.request.urlopen('https://raw.githubusercontent.com/pyodide/pyodide/0.28.3/LICENSE' if name=='LICENSE' else BASE+name,timeout=90) as response:data=response.read()
            if expected and hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Runtime integrity mismatch: '+name)
            path.write_bytes(data)
        shutil.copy2(path,output/name)
        return path.read_bytes()
    lock=json.loads(download('pyodide-lock.json',LOCK_SHA));names=set()
    def dependency(name):
        if name in names:return
        names.add(name)
        for child in lock['packages'][name]['depends']:dependency(child)
    for name in ('opencv-python','numpy','pillow'):dependency(name)
    files=[(name,None) for name in ('LICENSE','pyodide.js','pyodide.mjs','pyodide.asm.js','pyodide.asm.wasm','python_stdlib.zip')]
    files += [(lock['packages'][name]['file_name'],lock['packages'][name]['sha256']) for name in names]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for _ in pool.map(lambda args:download(*args),files):pass
    (output/'runtime-version.json').write_text(json.dumps({'pyodide':VERSION,'lock_sha256':LOCK_SHA,'packages':sorted(names),'source':BASE}),encoding='utf8')
    print('Runtime files:',len(files)+2,'bytes:',sum(file.stat().st_size for file in output.iterdir()))
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('output');parser.add_argument('--cache',default='.runtime-cache');args=parser.parse_args();vendor(args.output,args.cache)
