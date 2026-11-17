"""Latest-intent transition routing. Pure state; no Qt or service dependencies."""
from collections import deque

EDGES={
    ('idle','listening'):'assets/listening_v3_transition_aligned.mp4',
    ('listening','thinking'):'assets/thinking_v3_transition_aligned.mp4',
    # Prefer cancellation over briefly entering Speaking when returning to Idle.
    ('thinking','listening'):'assets/thinking_v3_cancel.mp4',
    ('thinking','speaking'):'assets/speaking_v3_entry_aligned.mp4',
    ('speaking','idle'):'assets/speaking_v3_return_aligned.mp4',
    ('listening','idle'):'assets/listening_v3_cancel.mp4',
}
STATES=frozenset(('idle','listening','thinking','speaking'))

class TransitionFlow:
    def __init__(self):self.abort()
    def abort(self):
        self.node='idle';self.desired='idle';self.active=None
    def request(self,target):
        if target not in STATES:raise ValueError(target)
        self.desired=target
        return None if self.active else self._next()
    def _next(self):
        if self.node==self.desired:return None
        queue=deque([(self.node,[])])
        seen={self.node}
        while queue:
            node,path=queue.popleft()
            if node==self.desired:
                self.active=path[0];return self.active
            for (a,b),file in EDGES.items():
                if a==node and b not in seen:
                    seen.add(b);queue.append((b,path+[(a,b,file)]))
        raise ValueError('No transition route')
    def finish(self):
        if self.active is None:return None
        self.node=self.active[1];self.active=None
        return self._next()
