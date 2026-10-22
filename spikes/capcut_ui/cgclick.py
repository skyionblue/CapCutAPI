"""Real CGEvent mouse clicks — CEF apps ignore System Events 'click at'."""
import time
import Quartz as Q

def _post(ev):
    Q.CGEventPost(Q.kCGHIDEventTap, ev)

def move(x, y):
    _post(Q.CGEventCreateMouseEvent(None, Q.kCGEventMouseMoved, (x, y), Q.kCGMouseButtonLeft))

def click(x, y, clicks=1, delay=0.06):
    move(x, y)
    time.sleep(delay)
    for n in range(1, clicks + 1):
        for kind in (Q.kCGEventLeftMouseDown, Q.kCGEventLeftMouseUp):
            ev = Q.CGEventCreateMouseEvent(None, kind, (x, y), Q.kCGMouseButtonLeft)
            Q.CGEventSetIntegerValueField(ev, Q.kCGMouseEventClickState, n)
            _post(ev)
            time.sleep(0.02)
        time.sleep(0.04)

def cursor():
    return Q.CGEventGetLocation(Q.CGEventCreate(None))
