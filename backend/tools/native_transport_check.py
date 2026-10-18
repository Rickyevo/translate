"""Owned-process native integration check: capture, backpressure, stop and reconnect.
All payloads are synthetic, no desktop input or external services. Counts only.
"""
import json,queue,subprocess as S,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from translate_backend.wetype.native_transport import Connection,NativeError,SIZE,run,STOPPED
from translate_backend.wetype.encode import composition,candidates
FIXTURE=ROOT/'.cache/feasibility-bin/feasibility_fixture.exe'
def start():
    p=S.Popen([str(FIXTURE)],stdin=S.PIPE,stdout=S.PIPE,text=True,encoding='utf-8',creationflags=0x08000000)
    assert json.loads(p.stdout.readline())['pid']==p.pid
    return p
def ask(p,command):
    p.stdin.write(command+'\n');p.stdin.flush();return json.loads(p.stdout.readline())
def finish(p):
    if p.poll()is None:p.stdin.write('quit\n');p.stdin.flush();p.wait(5)
    assert p.returncode==0
report={'shared_mapping_bytes':SIZE,'cases':[]}
p=start();connection=None
try:
    for cycle in range(3):
        connection=Connection(p.pid)
        events=queue.Queue();halt=threading.Event();errors=[];received=[]
        def drain():
            try:
                while not halt.is_set():
                    if not connection.poll(events.put,cycle+1):connection.wait(20)
            except Exception as error:errors.append(type(error).__name__)
        reader=threading.Thread(target=drain);reader.start()
        def collect(expected):
            end=time.monotonic()+5
            while len(received)<expected and time.monotonic()<end:
                try:ev=events.get(timeout=.1)
                except queue.Empty:continue
                if ev['kind']=='bytes':received.append(ev['data'])
                ev['_ack']()
            assert len(received)==expected,(len(received),expected,errors)
        payload=composition('ni')+candidates(['你好','😀'])
        for mode in ['write','nt','async']:
            before=len(received)
            # Dispatch on this thread concurrently with fixture I/O.
            result=[]
            writer=threading.Thread(target=lambda:result.append(ask(p,f'{mode} 20 {payload.hex()}')))
            writer.start();collect(before+20);writer.join(5)
            assert result[0]['delivered']==20*len(payload) and not result[0]['errors']
            assert all(data==payload for data in received[before:])
        big=bytes(range(256))*1024
        before=len(received);result=[]
        writer=threading.Thread(target=lambda:result.append(ask(p,'write 1 '+big.hex())))
        writer.start();collect(before+8);writer.join(5)
        assert b''.join(received[before:])==big
        halt.set();reader.join(1);assert not errors,errors
        # Discard remaining wakeups/acks before deliberate consumer pressure.
        while not events.empty():events.get()['_ack']()
        pressure=ask(p,f'write 100 {payload.hex()}')
        assert pressure['delivered']==100*len(payload) and not pressure['errors']
        assert not connection.healthy,'overflow must reject stale insertion immediately'
        seen=[]
        connection.poll(seen.append,cycle+1)
        assert seen and seen[0]['kind']=='gap'
        seen[0]['_ack']()
        while connection.poll(lambda e:e['_ack'](),cycle+1):pass
        assert connection.healthy
        # A fresh composition is readable after the loss and source reset.
        ask(p,f'nt 1 {payload.hex()}');seen=[]
        connection.poll(seen.append,cycle+1)
        assert len(seen)==1 and seen[0]['data']==payload
        seen[0]['_ack']()
        report['cases'].append({'cycle':cycle,'normal_writes':60,'max_write_bytes':len(big),
                                'overflow_detected':True,'original_pressure_writes_delivered':100,
                                'loss_count':connection._load64(32),'recovered':True})
        connection.close();connection=None
        # The original write still works after lease shutdown.
        assert ask(p,f'write 1 {payload.hex()}')['delivered']==len(payload)
    finish(p)
    # Process death and a new PID are distinct leases; old handles cannot be reused.
    p=start();connection=Connection(p.pid);p.kill();p.wait()
    try:connection.poll(lambda e:None,99)
    except NativeError:report['process_exit_detected']=True
    else:raise AssertionError('dead process accepted')
    connection.close();connection=None
    p=start();connection=Connection(p.pid)
    assert connection.healthy;report['new_process_reconnected']=True
    connection.close();connection=None;finish(p)
    # Python dispatch is bounded independently of the native producer ring.
    p=start();connection=Connection(p.pid);pending=[]
    ask(p,f'write 20 {payload.hex()}')
    connection.poll(pending.append,100)
    assert len(pending)==8
    connection.poll(pending.append,100);assert len(pending)==8
    for event in pending:event['_ack']()
    pending=[];connection.poll(pending.append,100);assert len(pending)==8
    for event in pending:event['_ack']()
    report['dispatch_pending_limit']=8
    # A stopped heartbeat releases the remote lease even if the owner stays alive.
    deadline=time.monotonic()+7
    while connection.state!=STOPPED and time.monotonic()<deadline:time.sleep(.05)
    assert connection.state==STOPPED
    connection.close();connection=None
    connection=Connection(p.pid);assert connection.healthy
    connection.close();connection=None
    report['heartbeat_expiry_and_reattach']=True
    # A crashed controller cannot run close(); the watchdog must recover anyway.
    code="import sys,time;sys.path.insert(0,sys.argv[1]);from translate_backend.wetype.native_transport import Connection;c=Connection(int(sys.argv[2]));print('ready',flush=True);time.sleep(30)"
    owner=S.Popen([sys.executable,'-B','-c',code,str(ROOT/'backend'),str(p.pid)],stdout=S.PIPE,text=True,creationflags=0x08000000)
    try:
        assert owner.stdout.readline().strip()=='ready'
        owner.kill();owner.wait(5)
        deadline=time.monotonic()+8
        while True:
            try:connection=Connection(p.pid);break
            except NativeError:
                if time.monotonic()>deadline:raise
                time.sleep(.2)
        assert connection.healthy
        connection.close();connection=None
        report['controller_crash_and_reattach']=True
    finally:
        if owner.poll()is None:owner.kill();owner.wait()
    # Exercise the real manager, including PID replacement and shutdown.
    halt=threading.Event();events=queue.Queue();target=[p.pid];leases=[]
    manager=threading.Thread(target=run,args=(events.put,halt,leases.append),kwargs={'lookup':lambda:target[0]})
    manager.start()
    try:
        def connected_after(epoch):
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                e=events.get(timeout=8)
                if e.get('state')=='connected' and e['epoch']>epoch:return e['epoch']
            raise AssertionError('manager did not reconnect')
        first=connected_after(0);p.kill();p.wait();p=start();target[0]=p.pid
        second=connected_after(first)
        assert leases[-1].pid==p.pid and leases[-1].healthy
        report['manager_pid_restart']=second>first
    finally:
        halt.set();manager.join(3)
        assert not manager.is_alive()
    assert leases[-1].closed
    cancelled=threading.Event();cancelled.set()
    try:Connection(p.pid,stop=cancelled)
    except NativeError as error:assert str(error)=='native_attach_cancelled'
    else:raise AssertionError('cancelled attach continued')
    report['attach_shutdown_cancelled']=True
    # The dispatch thread can check insertion health while transport shuts down.
    deadline=time.monotonic()+7
    while True:
        try:connection=Connection(p.pid);break
        except NativeError:
            if time.monotonic()>deadline:raise
            time.sleep(.1)
    checking=threading.Event();errors=[]
    def health_checks():
        try:
            while not checking.is_set():_ = connection.healthy
        except Exception as error:errors.append(type(error).__name__)
    checker=threading.Thread(target=health_checks);checker.start()
    connection.close();checking.set();checker.join(2)
    assert not errors and not checker.is_alive() and not connection.healthy
    connection=None
    report['health_check_shutdown_race']=True
    finish(p)
    (ROOT/'measurements/native-transport-integration-20261018.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)
finally:
    if connection:connection.close()
    if p.poll()is None:p.kill();p.wait()
