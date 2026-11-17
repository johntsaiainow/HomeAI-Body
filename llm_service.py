"""Manage only Neris-started LM Studio HTTP servers; never unload models/kill LM Studio."""
import http.client
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/'config/llm-service.json'
STATE=ROOT/'private/llm-service-owner.json'


def config():
    defaults={'enabled':False,'port':1234,'cli':str(Path.home()/'.lmstudio/bin/lms'),
              'autoload_model':True,'stop_owned_server_on_exit':True,'model':'','provider':'neris-a'}
    try:defaults.update(json.loads(CONFIG.read_text()))
    except FileNotFoundError:pass
    return defaults


def run(cli,args,timeout=30):
    result=subprocess.run([cli,*args],capture_output=True,text=True,timeout=timeout)
    directory=ROOT/'logs';directory.mkdir(exist_ok=True)
    with (directory/'llm-service.log').open('a') as out:
        out.write(time.strftime('%Y-%m-%d %H:%M:%S')+' lms '+ ' '.join(args)+'\n')
        out.write(result.stdout+result.stderr+'\n')
    if result.returncode:raise RuntimeError('LM Studio command failed; see logs/llm-service.log')
    return result.stdout


def server_status(cli):
    try:return json.loads(run(cli,['server','status','--json'],15))
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):return {'running':False}


def occupied(port):
    with socket.socket() as client:
        client.settimeout(1)
        return client.connect_ex(('127.0.0.1',port))==0


def reachable(port):
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
    try:
        connection.request('GET','/v1/models')
        response=connection.getresponse()
        return response.status in (200,401,403)  # Protected servers remain valid; no credential is read here.
    except (OSError,http.client.HTTPException):return False
    finally:connection.close()


def daemon_identity(cli):
    try:
        text=run(cli,['daemon','status'],15)
        match=re.search(r'PID:\s*(\d+)',text)
        if not match:return None
        pid=int(match.group(1))
        # /proc stat comm may contain spaces; fields after ')' start at field 3.
        fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        if Path(f'/proc/{pid}').stat().st_uid!=os.getuid():return None
        return {'pid':pid,'start_ticks':fields[19],
                'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    except (OSError,RuntimeError,subprocess.TimeoutExpired,IndexError):return None


def save_owner(cli,port):
    identity=daemon_identity(cli)
    if identity is None:return False  # No verifiable ownership => never stop it later.
    STATE.parent.mkdir(exist_ok=True,mode=0o700)
    temporary=STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps({'identity':identity,'port':port,'cli':cli},indent=2))
    temporary.chmod(0o600);temporary.replace(STATE)
    return True


def selected_model(cfg):
    if cfg.get('model'):return cfg['model']
    selection={}
    for path in (Path.home()/'.pi/agent/settings.json',ROOT/'.pi/settings.json'):
        try:selection.update(json.loads(path.read_text()))
        except (OSError,ValueError):pass
    if selection.get('defaultProvider')!=cfg['provider']:return None
    return selection.get('defaultModel')


def model_ready(cfg):
    expected=selected_model(cfg)
    if not expected:return False,'Server ready; no local model configured'
    rows=json.loads(run(cfg['cli'],['ps','--json'],20))
    if isinstance(rows,dict):rows=rows.get('models',[])
    if any(row.get('identifier')==expected for row in rows):return True,'LLM server and model ready'
    if rows:return False,'Server ready; another model is loaded, left untouched'
    if not cfg['autoload_model']:return False,'Server ready; selected model is not loaded'
    run(cfg['cli'],['load',expected,'--identifier',expected,'--yes','--no-engine-config-file'],180)
    rows=json.loads(run(cfg['cli'],['ps','--json'],20))
    if isinstance(rows,dict):rows=rows.get('models',[])
    ready=any(row.get('identifier')==expected for row in rows)
    return ready,'LLM server and model ready' if ready else 'Server ready; model load unconfirmed'


def ensure():
    try:
        cfg=config()
        if not cfg['enabled']:return {'server_ready':False,'model_ready':False,'message':'LLM auto-start disabled'}
        port=int(cfg['port'])
        if not 1<=port<=65535:raise ValueError('Invalid LLM server port')
        cli=str(Path(cfg['cli']).expanduser())
        cfg['cli']=cli
        if not Path(cli).is_file():raise RuntimeError('LM Studio CLI not found')
        status=server_status(cli)
        if status.get('running'):
            if status.get('port')!=port:raise RuntimeError('LM Studio is already serving another port; left untouched')
        else:
            if occupied(port):raise RuntimeError('LLM port already occupied; no service was replaced')
            # Clear stale ownership before a fresh launch; never adopt pre-existing servers.
            STATE.unlink(missing_ok=True)
            run(cli,['daemon','up'],45)
            run(cli,['server','start','--port',str(port),'--bind','127.0.0.1'],45)
            if not server_status(cli).get('running'):raise RuntimeError('LLM server start unconfirmed')
            save_owner(cli,port)
        if not reachable(port):raise RuntimeError('LLM HTTP endpoint is not ready')
        try:ready,message=model_ready(cfg)
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):
            ready=False;message='Server ready; model load/check failed (see LLM log)'
        return {'server_ready':True,'model_ready':ready,'message':message}
    except (OSError,ValueError,TypeError,RuntimeError,subprocess.TimeoutExpired) as error:
        return {'server_ready':False,'model_ready':False,'message':str(error)}


def stop_owned():
    try:
        cfg=config()
        if not cfg.get('enabled') or not cfg.get('stop_owned_server_on_exit'):return 'Shared LLM server left running'
        if not STATE.exists():return 'Pre-existing LLM server left running'
        owner=json.loads(STATE.read_text())
        cli=str(Path(cfg['cli']).expanduser())
        if owner.get('cli')!=cli or owner.get('port')!=int(cfg['port']) or owner.get('identity')!=daemon_identity(cli):
            STATE.unlink(missing_ok=True)
            return 'LLM ownership no longer matches; server left running'
        status=server_status(cli)
        if status.get('running') and status.get('port')==owner['port']:
            run(cli,['server','stop'],30)
            if server_status(cli).get('running'):return 'LLM server stop unconfirmed; ownership retained'
        STATE.unlink(missing_ok=True)
        return 'Neris-owned LLM HTTP server stopped; models/LM Studio left untouched'
    except (OSError,ValueError,TypeError,RuntimeError,subprocess.TimeoutExpired):
        return 'Could not safely stop owned LLM server; left untouched'
