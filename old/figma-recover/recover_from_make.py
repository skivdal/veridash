import json,re,os,shutil,hashlib
from pathlib import Path
ROOT=Path('/mnt/data/veridash_recovery')
D=json.load(open(ROOT/'extracted/ai_chat.json',encoding='utf-8'))['threads'][0]
OUT=ROOT/'recovered_project'; shutil.rmtree(OUT,ignore_errors=True); OUT.mkdir(parents=True)

def norm(p): return p.lstrip('/')
# calls/results
calls={}; results={}
for m in D['messages']:
 for part in m.get('parts',[]):
  pt=part.get('partType','')
  try:c=json.loads(part.get('contentJson','{}'))
  except:continue
  if pt.startswith('tool-call-json'):
   try:a=json.loads(c.get('argsJson','{}'))
   except:a={}
   calls[c.get('toolCallId')]={'name':c.get('toolName'),'args':a,'idx':m['index']}
  elif pt.startswith('tool-result-json'):
   try:r=json.loads(c.get('resultJson','{}'))
   except:r={}
   results[c.get('toolCallId')]={'result':r,'idx':m['index'],'name':c.get('toolName')}

def parse_numbered(s):
 # Remove reminder and parse N\t lines. Require contiguous.
 s=s.split('\n<system-reminder>')[0]
 ls=[]
 for line in s.splitlines():
  m=re.match(r'^(\d+)\t(.*)$',line)
  if not m: continue
  ls.append((int(m.group(1)),m.group(2)))
 if not ls:return None
 nums=[n for n,_ in ls]
 if nums != list(range(nums[0],nums[-1]+1)): return None
 return nums[0],nums[-1],'\n'.join(x for _,x in ls)+'\n'

# collect file observations
obs={}
for cid,c in calls.items():
 n=c['name']; a=c['args']; p=a.get('path')
 if not p or n not in ('view_tool','read'): continue
 rr=results.get(cid,{}).get('result',{})
 if not rr.get('success'):continue
 cont=rr.get('content','')
 parsed=parse_numbered(cont) if isinstance(cont,str) else None
 if parsed:
  start,end,text=parsed
  obs.setdefault(norm(p),[]).append((c['idx'],start,end,text))
 else:
  # some read calls return raw file content; directory listings are marked message
  if n=='read' and isinstance(cont,str) and cont and not rr.get('message','').startswith('Directory listing'):
   obs.setdefault(norm(p),[]).append((c['idx'],1,None,cont))

# mutation list by file
muts={}
for cid,c in calls.items():
 if c['name'] not in ('write_tool','edit_tool','fast_apply_tool'):continue
 p=c['args'].get('path');
 if not p:continue
 rr=results.get(cid,{}).get('result',{})
 if not rr.get('success'): continue
 muts.setdefault(norm(p),[]).append((c['idx'],c['name'],c['args']))
for v in muts.values():v.sort(key=lambda x:x[0])

report=[]; states={}
allpaths=set(obs)|set(muts)
for p in sorted(allpaths):
 # Pick the latest likely-complete snapshot: numbered starting at 1 and, preferably, very long.
 candidates=[]
 for o in obs.get(p,[]):
  idx,start,end,text=o
  if start==1:
   candidates.append(o)
 # We need a snapshot that is actually complete. Heuristic: for generated text files, latest long start=1 is usually full;
 # if a later start=1 is only <=100 lines while older is >500, favor older long snapshot.
 snap=None
 if candidates:
  maxend=max((x[2] or len(x[3].splitlines())) for x in candidates)
  viable=[x for x in candidates if (x[2] or 0)>=max(200,int(maxend*.8))]
  snap=max(viable or candidates,key=lambda x:x[0])
 state=None; baseidx=-1
 if snap:
  baseidx=snap[0]; state=snap[3]
 # If no useful snapshot, start from earliest successful write
 if state is None:
  ws=[x for x in muts.get(p,[]) if x[1]=='write_tool']
  if ws:
   idx,n,a=ws[0]; state=a.get('file_text',''); baseidx=idx
 # Apply subsequent exact writes/edits. Ignore fuzzy fast-apply, but report if after base.
 applied=failed=fuzzy=0
 for idx,n,a in muts.get(p,[]):
  if idx<=baseidx: continue
  if n=='write_tool': state=a.get('file_text',''); applied+=1; continue
  if n=='fast_apply_tool': fuzzy+=1; continue
  if state is None: failed+=1; continue
  old=a.get('old_str',''); new=a.get('new_str','')
  if old in state:
   # edit_tool replaces one exact occurrence; usually unique
   state=state.replace(old,new,1); applied+=1
  else:
   failed+=1
 # If state and text-ish path, write
 if state is not None and ('.' in Path(p).name):
  dest=OUT/p; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(state,encoding='utf-8')
  states[p]=state
  report.append((p,baseidx,applied,failed,fuzzy,len(state.splitlines())))

# Special recovery: App.tsx. Figma's view tool paginates large files into consecutive
# numbered chunks even though each call only says {path}. Around message 3907 it emitted
# lines 1-1482, 1483-2964, then 2965-3109: a complete late-file snapshot.
p='src/app/App.tsx'
chunks=[x for x in obs.get(p,[]) if 3907 <= x[0] <= 3911]
chunks.sort(key=lambda x:x[1])
if chunks and chunks[0][1]==1:
 expected=1; pieces=[]; ok=True
 for idx,st,en,text in chunks:
  if st!=expected: ok=False; break
  pieces.append(text); expected=en+1
 if ok:
  state=''.join(pieces); base=max(x[0] for x in chunks); applied=failed=0
  for idx,n,a in muts[p]:
   if idx<=base:continue
   if n=='edit_tool':
    if a['old_str'] in state:state=state.replace(a['old_str'],a['new_str'],1);applied+=1
    else: failed+=1
   elif n=='write_tool':state=a['file_text'];applied+=1
   elif n=='fast_apply_tool': failed+=1
  (OUT/p).write_text(state,encoding='utf-8'); states[p]=state
  report=[r for r in report if r[0]!=p]; report.append((p,base,applied,failed,0,len(state.splitlines())))

# Same pagination pattern for the final HelpCenter.tsx views immediately before its last edit.
p='src/imports/HelpCenter/HelpCenter.tsx'
chunks=[x for x in obs.get(p,[]) if x[0]>=4148]
chunks.sort(key=lambda x:x[1])
if chunks and chunks[0][1]==1:
 expected=1; pieces=[]; ok=True
 for idx,st,en,text in chunks:
  if st!=expected: ok=False; break
  pieces.append(text); expected=en+1
 if ok:
  state=''.join(pieces); base=max(x[0] for x in chunks); applied=failed=0
  for idx,n,a in muts.get(p,[]):
   if idx<=base:continue
   if n=='edit_tool':
    if a['old_str'] in state: state=state.replace(a['old_str'],a['new_str'],1); applied+=1
    else: failed+=1
  (OUT/p).write_text(state,encoding='utf-8'); states[p]=state
  report=[r for r in report if r[0]!=p]; report.append((p,base,applied,failed,0,len(state.splitlines())))

# Copy every binary blob to an asset pool, and resolve hash-named imports directly when names occur in source.
assetpool=OUT/'recovered-assets-by-hash'; assetpool.mkdir(exist_ok=True)
for folder in ('images','make_binary_files'):
 for f in (ROOT/'extracted'/folder).glob('*'):
  if f.is_file(): shutil.copy2(f,assetpool/f.name)
# Populate hash-named PNG imports at their exact referenced paths.
alltext='\n'.join(states.values())
imports=set(re.findall(r"['\"]([^'\"]+\.(?:png|jpg|jpeg|svg|webp))['\"]",alltext,re.I))
resolved=[]; unresolved=[]
# map blob hash to source binary: prefer make_binary_files, then images
blobdirs=[ROOT/'extracted'/'make_binary_files',ROOT/'extracted'/'images']
for imp in imports:
 name=Path(imp).name
 stem=Path(name).stem
 src=None
 if re.fullmatch(r'[0-9a-f]{40}',stem):
  for bd in blobdirs:
   if (bd/stem).exists(): src=bd/stem; break
 if src:
  # Find likely absolute project destination by resolving import against source file dirs.
  for sp,txt in states.items():
   if imp in txt:
    dest=(OUT/Path(sp).parent/imp).resolve()
    try: dest.relative_to(OUT.resolve())
    except: continue
    dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dest); resolved.append(str(dest.relative_to(OUT)))
 else: unresolved.append(imp)

# Add recovery README
with open(OUT/'RECOVERY_NOTES.md','w',encoding='utf-8') as f:
 f.write('# VeriDash Figma Make source recovery\n\n')
 f.write('Recovered from the exported `.make` archive by extracting literal file snapshots and replaying successful exact `write_tool`/`edit_tool` operations from `ai_chat.json`.\n\n')
 f.write('## Recovery report\n\n| File | Base message | Exact mutations applied | Failed exact mutations | Skipped successful fuzzy mutations | Lines |\n|---|---:|---:|---:|---:|---:|\n')
 for r in sorted(report): f.write('| `%s` | %s | %s | %s | %s | %s |\n'%r)
 f.write('\n## Assets\n\nAll binary blobs from the export are preserved in `recovered-assets-by-hash/`. Hash-named imports that could be matched exactly were copied into their referenced project paths.\n')
 if unresolved:
  f.write('\nUnresolved non-hash asset import strings found in recovered source:\n\n')
  for x in sorted(unresolved): f.write(f'- `{x}`\n')

print('FILES',len(states),'resolved assets',len(set(resolved)),'unresolved imports',len(set(unresolved)))
for r in sorted(report): print(r)
print('unresolved',sorted(set(unresolved))[:100])
