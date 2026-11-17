"""Allowlisted request telemetry; no prompts, answers, credentials or URLs persisted."""
import ipaddress
import json
import math
from pathlib import Path
import time
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'body/llm-status.json'


def selection():
    # Match the explicit router used by voice requests and desktop buttons,
    # not Pi's independent default settings.
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0,str(ROOT))
    try:
        import model_router
        mode,provider,model=model_router.current()
        return {'provider':provider,'model':model,
                'mode':'Cloud' if mode=='online' else 'Local'}
    except (OSError,ValueError,KeyError):
        return {'provider':'','model':'','mode':'Unknown'}


def provider_endpoint(provider):
    for path in (ROOT/'.pi/models.json',Path.home()/'.pi/agent/models.json'):
        try:
            row=json.loads(path.read_text()).get('providers',{}).get(provider,{})
            if row.get('baseUrl'):return row['baseUrl']
        except (OSError,ValueError,AttributeError):pass
    return None


def provider_mode(provider):
    endpoint=provider_endpoint(provider)
    if endpoint:
        host=urlparse(endpoint).hostname or ''
        if host=='localhost':return 'Local'
        try:
            if ipaddress.ip_address(host).is_private:return 'Local'
        except ValueError:pass
    return 'Cloud' if provider else 'Unknown'


def read():
    try:
        value=json.loads(STATE.read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def store(data):
    # Explicit allowlist protects against inadvertently persisting provider config/secrets.
    keys=('provider','model','mode','status','input','output','cache_read','cache_write','total',
          'elapsed','effective_rate','estimated_cost','usage_available','calls','updated_at')
    clean={key:data[key] for key in keys if key in data}
    STATE.parent.mkdir(exist_ok=True)
    temporary=STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(clean,ensure_ascii=False,indent=2))
    temporary.replace(STATE)


def begin():
    data=read();current=selection()
    if (data.get('provider'),data.get('model'))!=(current['provider'],current['model']):data={}
    data.update(current);data.update(status='Thinking',updated_at=time.time())
    store(data)


def failed(status='Failed'):
    data=read();data.update(status=status,updated_at=time.time());store(data)


class ModelUnavailableError(RuntimeError):
    """Service explicitly rejected the selected model; never expose raw diagnostics."""


def parse_result(stdout,elapsed):
    messages=[]
    for line in stdout.split('\n'):  # JSONL is LF-delimited, not Unicode splitlines.
        try:event=json.loads(line)
        except ValueError:continue
        if not isinstance(event,dict):continue
        if event.get('type')=='message_end' and isinstance(event.get('message'),dict):
            message=event['message']
            if message.get('role')=='assistant':messages.append(message)
    if not messages:raise ValueError('No completed assistant message in Pi JSON stream')
    last=messages[-1]
    reply=''.join(block.get('text','') for block in last.get('content',[]) if block.get('type')=='text')
    if last.get('stopReason') in ('error','aborted'):
        diagnostic=str(last.get('errorMessage','')).lower()
        if 'model_not_found' in diagnostic or ('model' in diagnostic and 'not supported' in diagnostic):
            raise ModelUnavailableError('Selected model is unavailable for this account')
        raise RuntimeError('Pi request failed')
    totals={key:0 for key in ('input','output','cacheRead','cacheWrite','totalTokens')}
    cost=0.;has_cost=False
    for message in messages:
        usage=message.get('usage') or {}
        for key in totals:
            value=usage.get(key)
            if isinstance(value,(int,float)) and math.isfinite(value) and value>=0:totals[key]+=value
        value=usage.get('cost',{}).get('total')
        if isinstance(value,(int,float)) and math.isfinite(value) and value>0:cost+=value;has_cost=True
    available=any(totals.values())
    provider=last.get('provider','');model=last.get('model','')
    data={'provider':provider,'model':model,'mode':provider_mode(provider),'status':'Ready',
          'input':totals['input'] if available else None,'output':totals['output'] if available else None,
          'cache_read':totals['cacheRead'] if available else None,'cache_write':totals['cacheWrite'] if available else None,
          'total':totals['totalTokens'] if available else None,'elapsed':elapsed,
          'effective_rate':totals['output']/elapsed if available and elapsed>0 else None,
          'estimated_cost':cost if has_cost else None,'usage_available':available,'calls':len(messages),'updated_at':time.time()}
    return reply,data
