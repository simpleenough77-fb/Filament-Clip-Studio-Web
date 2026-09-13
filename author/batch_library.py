"""Validated local drafts and named batches; no geometry or catalog edits."""
import json, os, re
from pathlib import Path
from datetime import datetime, timezone

FIELDS=('printer','font','type_size','vendor_size','color_size','style','body_mode','text_mode')
def clean_draft(data, validate):
    if not isinstance(data,dict) or not isinstance(data.get('rows'),list):
        raise ValueError('Invalid batch data.')
    raw=data.get('settings',{})
    if not isinstance(raw,dict):raise ValueError('Invalid preferences.')
    settings={k:raw[k] for k in FIELDS if k in raw}
    rows=validate(dict(rows=data['rows'],settings=settings),allow_empty=True)['rows']
    return dict(rows=rows,settings=settings)

def load(path):
    if not path.exists():return dict(version=1,draft=None,preferences={},batches={})
    return json.loads(path.read_text())

def save(path,state):
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(state,ensure_ascii=False,indent=2))
    os.replace(temp,path)

def update(path,data,validate):
    state=load(path); action=data.get('action','draft')
    draft=clean_draft(data.get('draft'),validate)
    if action=='batch':
        name=str(data.get('name','')).strip()
        if not 1<=len(name)<=80:raise ValueError('Name your batch using 1–80 characters.')
        if not draft['rows']:raise ValueError('Add labels before saving a named batch.')
        key=name.casefold()
        if key not in state['batches'] and len(state['batches'])>=100:raise ValueError('The library holds up to 100 named batches.')
        prior=state['batches'].get(key)
        history=((prior.get('history',[])+[dict(draft=prior['draft'],updated=prior['updated'])])[-10:]) if prior else []
        state['batches'][key]=dict(name=name,draft=draft,history=history,updated=datetime.now(timezone.utc).isoformat())
    elif action!='draft':raise ValueError('Unknown library action.')
    state['draft']=draft;state['preferences']=draft['settings'];save(path,state)
    return state

