"""Thread-safe cancellable work queue; Tk callbacks remain on the main thread."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import inspect
import queue
import threading
import uuid


@dataclass(frozen=True)
class TaskEvent:
    task_id:str; kind:str; payload:object=None


class TaskWorker:
    def __init__(self,max_workers=16):
        self.executor=ThreadPoolExecutor(max_workers=max_workers,thread_name_prefix="bpmn-gui")
        self.events=queue.Queue(); self.cancellations={}; self.futures={}

    def submit(self,function,*args,**kwargs):
        task_id=str(uuid.uuid4()); cancel_event=threading.Event(); self.cancellations[task_id]=cancel_event
        def run():
            self.events.put(TaskEvent(task_id,"started"))
            if cancel_event.is_set(): self.events.put(TaskEvent(task_id,"cancelled")); return
            try:
                signature=inspect.signature(function)
                result=(function(*args,cancel_event=cancel_event,**kwargs)
                        if "cancel_event" in signature.parameters else function(*args,**kwargs))
                self.events.put(TaskEvent(task_id,"cancelled" if cancel_event.is_set() else "completed",result))
            except Exception as exc:
                self.events.put(TaskEvent(task_id,"error",{"type":type(exc).__name__,"message":str(exc)}))
        self.futures[task_id]=self.executor.submit(run); return task_id

    def cancel(self,task_id):
        if task_id in self.cancellations: self.cancellations[task_id].set()

    def poll(self):
        result=[]
        while True:
            try: result.append(self.events.get_nowait())
            except queue.Empty: return tuple(result)

    def shutdown(self):
        for event in self.cancellations.values(): event.set()
        self.executor.shutdown(wait=True,cancel_futures=True)
