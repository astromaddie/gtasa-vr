"""Native PNG upload regression: oversized source must not overwrite raster guards."""
from pathlib import Path
import subprocess,tempfile,argparse
p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--rgb',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
 exe=Path(tmp)/'test.exe'
 source=a.source or root/'native/tests/png-raster-upload.cpp'
 command=f'call "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat" >nul && cl /nologo /std:c++20 /EHsc /W4 /I"{root / "native/src"}" "{source}" /Fe:"{exe}" /Fo:"{Path(tmp)/"test.obj"}" && "{exe}"'
 if a.rgb:command+=f' "{a.rgb}"'
 batch=Path(tmp)/'run.bat';batch.write_text('@echo off\n'+command+'\n',encoding='utf8')
 subprocess.run(['cmd.exe','/d','/c',str(batch)],check=True)
