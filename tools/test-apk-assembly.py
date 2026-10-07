#!/usr/bin/env python3
"""Regress classic APK ZIP headers and Frame-vs-Quest signing policy."""
import ast,importlib.util,struct,sys,tempfile,zipfile,subprocess
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parent.parent if len(sys.argv)==1 else Path(sys.argv[1])
spec=importlib.util.spec_from_file_location('savr_assemble',root/'tools/assemble.py');mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
with tempfile.TemporaryDirectory(prefix='savr-apk-test-') as d:
 p=Path(d);old=p/'source.apk';new=p/'new.apk'
 with zipfile.ZipFile(old,'w') as z:
  info=zipfile.ZipInfo('assets/preserved.bin');info.extra=b'\x35\xd9\x04\x00KEEP'
  with z.open(info,'w',force_zip64=True) as out:out.write(b'preserve'*128)
  z.writestr('classes.dex',b'old loader');z.writestr('META-INF/OLD.SF',b'old signature')
 previous=zipfile.ZIP64_LIMIT;zipfile.ZIP64_LIMIT=64 # Exercise unnecessary threshold without a multi-GB fixture.
 try:
  mod.rewrite_apk(old,new,{'classes.dex':b'new loader'},{'lib/arm64-v8a/libsavr.so':(b'new native',zipfile.ZIP_DEFLATED)})
  assert zipfile.ZIP64_LIMIT==64,'writer must restore the previous threshold'
 finally:zipfile.ZIP64_LIMIT=previous
 raw=new.read_bytes()
 assert b'PK\x06\x06' not in raw and b'PK\x06\x07' not in raw,'APK must not have ZIP64 EOCD/locator'
 with zipfile.ZipFile(new) as z:
  assert z.testzip() is None
  assert z.read('assets/preserved.bin')==b'preserve'*128
  assert z.read('classes.dex')==b'new loader'
  assert 'META-INF/OLD.SF' not in z.namelist()
  assert len(z.namelist())==len(set(z.namelist()))
  for info in z.infolist():
   local=struct.unpack_from('<4s5H3I2H',raw,info.header_offset)
   assert local[1]<45 and info.extract_version<45,'classic local and central header versions'
   assert local[7]!=0xffffffff and local[8]!=0xffffffff,'classic unsigned 32-bit sizes'
   cursor=0
   while cursor<len(info.extra):
    tag,size=struct.unpack_from('<HH',info.extra,cursor);assert tag!=1,'no stale ZIP64 extra';cursor+=4+size
  assert z.getinfo('assets/preserved.bin').extra==b'\x35\xd9\x04\x00KEEP'
 mod.audit_rewrite(old,new,{'classes.dex'},{'lib/arm64-v8a/libsavr.so'})
 zipalign=Path('/Users/mads/Library/Android/sdk/build-tools/35.0.0/zipalign')
 if zipalign.is_file():
  aligned=p/'aligned.apk';subprocess.run([str(zipalign),'-P','16','-f','4',str(new),str(aligned)],check=True)
  subprocess.run([str(zipalign),'-c','-P','16','4',str(aligned)],check=True)
 # Use the actual production guard, without running a complete package build.
 tree=ast.parse((root/'tools/assemble.py').read_text())
 guard=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and 'args.personal_update_source' in ast.unparse(n.test) and 'output_signer' in ast.unparse(n.test))
 probe=compile(ast.fix_missing_locations(ast.Module(body=[guard],type_ignores=[])),'production-signer-guard','exec')
 for frame,personal,same in [(False,True,False),(False,True,True),(True,True,False),(True,True,True),(False,False,False)]:
  env={'args':SimpleNamespace(steam_frame=frame,personal_update_source=personal),'package':SimpleNamespace(signer_sha256='old'),'output_signer':'old' if same else 'new','KitError':mod.KitError}
  rejected=False
  try:exec(probe,env)
  except mod.KitError:rejected=True
  assert rejected==(personal and not frame and not same),'Quest remains same-signer; Steam rebake allows a new signer'
print('PASS: production APK streaming headers, preserved entries, Android zipalign, and Frame/Quest signer guard')
