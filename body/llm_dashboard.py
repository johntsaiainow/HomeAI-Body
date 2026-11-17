"""Read-only LLM/hardware dashboard; background probes, no credentials in widgets."""
import json
from pathlib import Path
import shutil
import socket
import subprocess
import time
from urllib.parse import urlparse
from PySide6.QtCore import QThread,Signal,Qt
from PySide6.QtWidgets import QLabel,QSizePolicy
import llm_metrics


def number(value,decimals=0):
    if not isinstance(value,(int,float)):return '—'
    return f'{value:,.{decimals}f}'


def render(config,data,server,hardware):
    if (data.get('provider'),data.get('model'))!=(config.get('provider'),config.get('model')):data={}
    status=data.get('status','Waiting')
    if status=='Thinking' and time.time()-data.get('updated_at',0)>45:status='Stale'
    return '\n'.join([
        f"LLM: {config['mode']} | {config['provider'] or '—'}",
        config['model'] or '—',
        f"{server} | {status}",
        f"IN {number(data.get('input'))}  OUT {number(data.get('output'))}",
        f"Cache {number(data.get('cache_read'))}/{number(data.get('cache_write'))}  T {number(data.get('total'))}",
        f"{number(data.get('elapsed'),2)}s | {number(data.get('effective_rate'),1)} tok/s",
        f"Est. {'$'+number(data['estimated_cost'],6) if data.get('estimated_cost') is not None else '—'}",
        hardware,
    ])


def hardware_status():
    ram='System RAM: —'
    try:
        values={row.split(':')[0]:int(row.split()[1]) for row in Path('/proc/meminfo').read_text().splitlines()}
        total=values['MemTotal']/1024**2;used=(values['MemTotal']-values['MemAvailable'])/1024**2
        ram=f'System RAM: {used:.1f}/{total:.1f} GiB'
    except (OSError,ValueError,KeyError):pass
    gpu='GPU: —'
    executable=shutil.which('nvidia-smi')
    if executable:
        try:
            result=subprocess.run([executable,'--query-gpu=utilization.gpu,memory.used,memory.total',
                '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2)
            used_gpu,used,total=map(float,result.stdout.split('\n')[0].split(','))
            gpu=f'System GPU: {used_gpu:.0f}% | VRAM: {used/1024:.1f}/{total/1024:.1f} GiB'
        except (OSError,ValueError,subprocess.TimeoutExpired):pass
    return ram.replace('System RAM:','RAM').replace(' GiB','G')+'\n'+gpu.replace('System GPU:','GPU').replace(' | VRAM:','').replace(' GiB','G')


class MetricsWorker(QThread):
    changed=Signal(str)
    def run(self):
        hardware='System RAM: —\nGPU: —';last_hardware=0
        while not self.isInterruptionRequested():
            cfg=llm_metrics.selection();data=llm_metrics.read()
            server='On request'
            if cfg['mode']=='Local':
                endpoint=llm_metrics.provider_endpoint(cfg['provider'])
                parsed=urlparse(endpoint or 'http://127.0.0.1:1234')
                try:
                    with socket.create_connection((parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80)),timeout=.4):server='Reachable'
                except (OSError,ValueError):server='Unavailable'
            if time.monotonic()-last_hardware>5:
                hardware=hardware_status();last_hardware=time.monotonic()
            self.changed.emit(render(cfg,data,server,hardware))
            for _ in range(10):
                if self.isInterruptionRequested():return
                self.msleep(100)


class DashboardField:
    """Keep existing setText callers while moving their display into one header."""
    def __init__(self,dashboard,key,text):
        self.dashboard=dashboard;self.key=key;self.setText(text)
    def setText(self,text):
        self.value=text;self.dashboard.set_info(self.key,text)
    def text(self):return self.value


class MusicInfoLabel(QLabel):
    """Dedicated third header row; visibility follows music mode, not LLM refresh."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self._extra={};self._full_text=''
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.setStyleSheet('QLabel { color: #00ff66; background: #000000; font-family: monospace; font-size: 12px; padding: 6px; }')
        self.hide()
    def set_info(self,key,text):
        self._extra[key]=text
        beat=self._extra.get('beat','Beat sync: waiting for music')
        self._full_text='\n'.join([beat]+[self._extra[k] for k in ('repeat','control') if k in self._extra])
        self.setToolTip(self._full_text)
        self.fit_text()
    def fit_text(self):
        width=max(1,self.width()-12)
        self.setText('\n'.join(self.fontMetrics().elidedText(line,Qt.TextElideMode.ElideRight,width)
                               for line in self._full_text.split('\n')))
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'_full_text'):self.fit_text()


class MetricsLabel(QLabel):
    def __init__(self,parent=None):
        super().__init__('LLM: Loading status…',parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(False)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.setStyleSheet('QLabel { color: #00ff66; background: #000000; font-family: monospace; font-size: 12px; padding: 6px; }')
        self.setToolTip('Last LLM invocation totals; avg tok/s includes CLI startup and tool time. Cost is a configured-rate estimate, not a bill. RAM/GPU are system-wide. Server Reachable is a connection check, not authentication/model validation.')
        self._explanation=self.toolTip()
        self._base_text='LLM: Loading status…'
        self._extra={}
        self._full_text=self._base_text
        self.worker=MetricsWorker(self);self.worker.changed.connect(self.display);self.worker.start()
    def display(self,text):
        self._base_text=text
        self.refresh_text()
    def set_info(self,key,text):
        self._extra[key]=text
        self.refresh_text()
    def refresh_text(self):
        self._full_text=self._base_text+'\n'+'\n'.join(self._extra.values()) if self._extra else self._base_text
        self.setToolTip(self._full_text+'\n\n'+self._explanation)
        self.fit_text()
    def fit_text(self):
        width=max(1,self.width()-12)
        self.setText('\n'.join(self.fontMetrics().elidedText(line,Qt.TextElideMode.ElideRight,width)
                               for line in self._full_text.split('\n')))
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'_full_text'):self.fit_text()
    def shutdown(self):
        self.worker.requestInterruption();self.worker.wait()
