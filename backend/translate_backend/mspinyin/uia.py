"""Minimal stable UI Automation COM ABI used by the Microsoft Pinyin observer.

Unused vtable slots are retained as reserved methods and must never be called.
Signatures and GUIDs follow the Windows UIAutomationClient typelib shipped with
the existing application. No typelib parsing or generated wrappers are loaded.
"""
from ctypes import POINTER, HRESULT, c_int, c_void_p
from ctypes.wintypes import tagRECT
from comtypes import BSTR, CoClass, COMMETHOD, GUID, IUnknown
from comtypes.automation import VARIANT

TreeScope = c_int
TreeScope_Descendants = 4
UIA_MenuOpenedEventId = 20003
UIA_MenuClosedEventId = 20007
UIA_ControlTypePropertyId = 30003
UIA_NamePropertyId = 30005
UIA_ListItemControlTypeId = 50007

def _vtable(size, used):
    # Each reserved entry occupies one ABI slot; it is never invoked.
    return [used[i] if i in used else COMMETHOD([], HRESULT, f'_reserved_{i}')
            for i in range(size)]

class IUIAutomationElement(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{D22108AA-8AC5-49A5-837B-37BBB3D7591E}')
    _idlflags_ = []

class IUIAutomationElementArray(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{14314595-B4BC-4055-95F2-58F2E42C9855}')
    _idlflags_ = []

class IUIAutomationCacheRequest(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{B32A92B5-BC25-4078-9C08-D7EE95C48E03}')
    _idlflags_ = []

class IUIAutomationCondition(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{352FFBA8-0973-437C-A61F-F64CAFD81DF9}')
    _idlflags_ = []

class IUIAutomationEventHandler(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{146C3C17-F12E-4E22-8C27-F894B9B79C69}')
    _idlflags_ = ['oleautomation']

class IUIAutomation(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{30CBE57D-D9D0-452A-AB13-7AC5AC4825EE}')
    _idlflags_ = []

class IUIAutomationTreeWalker(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{4042C624-389C-4AFC-A630-9DF854A541FC}')
    _idlflags_ = []

IUIAutomationElement._methods_ = _vtable(82, {
    5: COMMETHOD([], HRESULT, 'FindAllBuildCache', (['in'], TreeScope, 'scope'), (['in'], POINTER(IUIAutomationCondition), 'condition'), (['in'], POINTER(IUIAutomationCacheRequest), 'cacheRequest'), (['out', 'retval'], POINTER(POINTER(IUIAutomationElementArray)), 'found')),
    17: COMMETHOD(['propget'], HRESULT, 'CurrentProcessId', (['out', 'retval'], POINTER(c_int), 'retVal')),
    26: COMMETHOD(['propget'], HRESULT, 'CurrentAutomationId', (['out', 'retval'], POINTER(BSTR), 'retVal')),
    35: COMMETHOD(['propget'], HRESULT, 'CurrentIsOffscreen', (['out', 'retval'], POINTER(c_int), 'retVal')),
    40: COMMETHOD(['propget'], HRESULT, 'CurrentBoundingRectangle', (['out', 'retval'], POINTER(tagRECT), 'retVal')),
    52: COMMETHOD(['propget'], HRESULT, 'CachedName', (['out', 'retval'], POINTER(BSTR), 'retVal')),
})

IUIAutomationEventHandler._methods_ = _vtable(1, {
    0: COMMETHOD([], HRESULT, 'HandleAutomationEvent', (['in'], POINTER(IUIAutomationElement), 'sender'), (['in'], c_int, 'eventId')),
})

IUIAutomation._methods_ = _vtable(55, {
    2: COMMETHOD([], HRESULT, 'GetRootElement', (['out', 'retval'], POINTER(POINTER(IUIAutomationElement)), 'root')),
    3: COMMETHOD([], HRESULT, 'ElementFromHandle', (['in'], c_void_p, 'hwnd'), (['out', 'retval'], POINTER(POINTER(IUIAutomationElement)), 'element')),
    11: COMMETHOD(['propget'], HRESULT, 'ControlViewWalker', (['out', 'retval'], POINTER(POINTER(IUIAutomationTreeWalker)), 'walker')),
    17: COMMETHOD([], HRESULT, 'CreateCacheRequest', (['out', 'retval'], POINTER(POINTER(IUIAutomationCacheRequest)), 'cacheRequest')),
    20: COMMETHOD([], HRESULT, 'CreatePropertyCondition', (['in'], c_int, 'propertyId'), (['in'], VARIANT, 'value'), (['out', 'retval'], POINTER(POINTER(IUIAutomationCondition)), 'newCondition')),
    29: COMMETHOD([], HRESULT, 'AddAutomationEventHandler', (['in'], c_int, 'eventId'), (['in'], POINTER(IUIAutomationElement), 'element'), (['in'], TreeScope, 'scope'), (['in'], POINTER(IUIAutomationCacheRequest), 'cacheRequest'), (['in'], POINTER(IUIAutomationEventHandler), 'handler')),
    38: COMMETHOD([], HRESULT, 'RemoveAllEventHandlers'),
})

IUIAutomationCondition._methods_ = _vtable(0, {
})

IUIAutomationElementArray._methods_ = _vtable(2, {
    0: COMMETHOD(['propget'], HRESULT, 'Length', (['out', 'retval'], POINTER(c_int), 'Length')),
    1: COMMETHOD([], HRESULT, 'GetElement', (['in'], c_int, 'index'), (['out', 'retval'], POINTER(POINTER(IUIAutomationElement)), 'element')),
})

IUIAutomationCacheRequest._methods_ = _vtable(9, {
    0: COMMETHOD([], HRESULT, 'AddProperty', (['in'], c_int, 'propertyId')),
})

IUIAutomationTreeWalker._methods_ = _vtable(13, {
    0: COMMETHOD([], HRESULT, 'GetParentElement', (['in'], POINTER(IUIAutomationElement), 'element'), (['out', 'retval'], POINTER(POINTER(IUIAutomationElement)), 'parent')),
})

class CUIAutomation(CoClass):
    _reg_clsid_ = GUID('{FF48DBA4-60EF-4201-AA87-54103EEF594E}')
    _com_interfaces_ = [IUIAutomation]
