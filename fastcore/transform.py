# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/04_transform.ipynb (unless otherwise specified).

__all__ = ['Transform', 'InplaceTransform', 'DisplayedTransform', 'ItemTransform', 'get_func', 'Func', 'Sig',
           'compose_tfms', 'mk_transform', 'gather_attrs', 'gather_attr_names', 'Pipeline']

# Cell
from .imports import *
from .foundation import *
from .utils import *
from .dispatch import *

# Cell
_tfm_methods = 'encodes','decodes','setups'

class _TfmDict(dict):
    def __setitem__(self,k,v):
        print("In _TfmDict: __setitem__")
        if k not in _tfm_methods or not callable(v): return super().__setitem__(k,v)
        if k not in self: super().__setitem__(k,TypeDispatch())
        self[k].add(v)

# Cell
class _TfmMeta(type):
    def __new__(cls, name, bases, dict):
        print("In _TfmMeta: __new__")
        res = super().__new__(cls, name, bases, dict)
        for nm in _tfm_methods:
            print("In _TfmMeta: nm ", nm)
            base_td = [getattr(b,nm,None) for b in bases]
            print("In _TfmMeta: base_td ", base_td)

            if nm in res.__dict__: 
                print("In _TfmMeta: nm in res.__dict__ ")
                getattr(res,nm).bases = base_td
            else: 
                print("In _TfmMeta: not in nm in res.__dict__ ")
                setattr(res, nm, TypeDispatch(bases=base_td))
        res.__signature__ = inspect.signature(res.__init__)
        return res

    def __call__(cls, *args, **kwargs):
        print("In metaclass _TfmMeta")
        f = args[0] if args else None
        print("In metaclass _TfmMeta f", f)
        n = getattr(f,'__name__',None)
        print("In metaclass _TfmMeta n", n)
        if callable(f) and n in _tfm_methods:
            print("In metaclass _TfmMeta callable(f) and n in _tfm_methods")
            getattr(cls,n).add(f)
            return f
        return super().__call__(*args, **kwargs)

    @classmethod
    def __prepare__(cls, name, bases): return _TfmDict()

# Cell
def _get_name(o):
    if hasattr(o,'__qualname__'): return o.__qualname__
    if hasattr(o,'__name__'): return o.__name__
    return o.__class__.__name__

# Cell
def _is_tuple(o): return isinstance(o, tuple) and not hasattr(o, '_fields')

import inspect 
# Cell
class Transform(metaclass=_TfmMeta):
    "Delegates (`__call__`,`decode`,`setup`) to (<code>encodes</code>,<code>decodes</code>,<code>setups</code>) if `split_idx` matches"
    split_idx,init_enc,order,train_setup = None,None,0,None
    def __init__(self, enc=None, dec=None, split_idx=None, order=None):
        self.split_idx = ifnone(split_idx, self.split_idx)
        if order is not None: self.order=order
        self.init_enc = enc or dec
        if not self.init_enc: return

        print("In Transform: about to TypeDispatch encodes, decodes, setups")
        self.encodes,self.decodes,self.setups = TypeDispatch(),TypeDispatch(),TypeDispatch()
        if enc:
            self.encodes.add(enc)
            self.order = getattr(enc,'order',self.order)
            if len(type_hints(enc)) > 0: self.input_types = first(type_hints(enc).values())
            self._name = _get_name(enc)
        if dec: self.decodes.add(dec)

    @property
    def name(self): return getattr(self, '_name', _get_name(self))
    def __call__(self, x, **kwargs): 
        print("In Transform: __call__ ")
        if self.name:
            print("In Transform: calling function ", self.name, " inspect source ", inspect.getsource(self.name))
        curframe = inspect.currentframe()
        print(inspect.getouterframes(curframe, 5))
        return self._call('encodes', x, **kwargs)
    def decode  (self, x, **kwargs): 
        print("In Tranfsorm: decode")
        return self._call('decodes', x, **kwargs)
    def __repr__(self): 
        return f'{self.name}:\nencodes: {self.encodes}decodes: {self.decodes}'

    def setup(self, items=None, train_setup=False):
        print("In Transform: setup:")
        train_setup = train_setup if self.train_setup is None else self.train_setup
        return self.setups(getattr(items, 'train', items) if train_setup else items)

    def _call(self, fn, x, split_idx=None, **kwargs):
        if split_idx!=self.split_idx and self.split_idx is not None: return x
        return self._do_call(getattr(self, fn), x, **kwargs)

    def _do_call(self, f, x, **kwargs):
        if not _is_tuple(x):
            if f is None: return x
            ret = f.returns_none(x) if hasattr(f,'returns_none') else None
            return retain_type(f(x, **kwargs), x, ret)
        res = tuple(self._do_call(f, x_, **kwargs) for x_ in x)
        return retain_type(res, x)

add_docs(Transform, decode="Delegate to <code>decodes</code> to undo transform", setup="Delegate to <code>setups</code> to set up transform")

# Cell
class InplaceTransform(Transform):
    "A `Transform` that modifies in-place and just returns whatever it's passed"
    def _call(self, fn, x, split_idx=None, **kwargs):
        super()._call(fn,x,split_idx,**kwargs)
        return x

# Cell
class DisplayedTransform(Transform):
    "A transform with a `__repr__` that shows its attrs"

    @property
    def name(self): return f"{super().name} -- {getattr(self,'__stored_args__',{})}"

# Cell
class ItemTransform(Transform):
    "A transform that always take tuples as items"
    _retain = True
    def __call__(self, x, **kwargs): return self._call1(x, '__call__', **kwargs)
    def decode(self, x, **kwargs):   return self._call1(x, 'decode', **kwargs)
    def _call1(self, x, name, **kwargs):
        if not _is_tuple(x): return getattr(super(), name)(x, **kwargs)
        y = getattr(super(), name)(list(x), **kwargs)
        if not self._retain: return y
        if is_listy(y) and not isinstance(y, tuple): y = tuple(y)
        return retain_type(y, x)

# Cell
def get_func(t, name, *args, **kwargs):
    "Get the `t.name` (potentially partial-ized with `args` and `kwargs`) or `noop` if not defined"
    f = getattr(t, name, noop)
    return f if not (args or kwargs) else partial(f, *args, **kwargs)

# Cell
class Func():
    "Basic wrapper around a `name` with `args` and `kwargs` to call on a given type"
    def __init__(self, name, *args, **kwargs): self.name,self.args,self.kwargs = name,args,kwargs
    def __repr__(self): return f'sig: {self.name}({self.args}, {self.kwargs})'
    def _get(self, t): return get_func(t, self.name, *self.args, **self.kwargs)
    def __call__(self,t): return mapped(self._get, t)

# Cell
class _Sig():
    def __getattr__(self,k):
        def _inner(*args, **kwargs): return Func(k, *args, **kwargs)
        return _inner

Sig = _Sig()

# Cell
def compose_tfms(x, tfms, is_enc=True, reverse=False, **kwargs):
    "Apply all `func_nm` attribute of `tfms` on `x`, maybe in `reverse` order"
    if reverse: tfms = reversed(tfms)
    for f in tfms:
        if not is_enc: f = f.decode
        x = f(x, **kwargs)
    return x

# Cell
def mk_transform(f):
    "Convert function `f` to `Transform` if it isn't already one"
    f = instantiate(f)
    return f if isinstance(f,(Transform,Pipeline)) else Transform(f)

# Cell
def gather_attrs(o, k, nm):
    "Used in __getattr__ to collect all attrs `k` from `self.{nm}`"
    if k.startswith('_') or k==nm: raise AttributeError(k)
    att = getattr(o,nm)
    res = [t for t in att.attrgot(k) if t is not None]
    if not res: raise AttributeError(k)
    return res[0] if len(res)==1 else L(res)

# Cell
def gather_attr_names(o, nm):
    "Used in __dir__ to collect all attrs `k` from `self.{nm}`"
    return L(getattr(o,nm)).map(dir).concat().unique()

# Cell
class Pipeline:
    "A pipeline of composed (for encode/decode) transforms, setup with types"
    def __init__(self, funcs=None, split_idx=None):
        print("In Pipeline")
        print("In Pipeline: funcs: ", funcs, " split_idx: ", split_idx)

        self.split_idx,self.default = split_idx,None

        if funcs is None: funcs = []
        if isinstance(funcs, Pipeline):
            print("In Pipeline: isinstance(funcs, Pipeline)")
            self.fs = funcs.fs
        else:
            print("In Pipeline: not isinstance(funcs, Pipeline)")
            if isinstance(funcs, Transform): funcs = [funcs]
            self.fs = L(ifnone(funcs,[noop])).map(mk_transform).sorted(key='order')
            print("In Pipeline: self.fs", self.fs)
            for f in self.fs:
                print("In Pipeline: f in self.fs type: ", type(f), " f ", f.name)

        for f in self.fs:
            print("In Pipeline: f", f.name)
            name = camel2snake(type(f).__name__)
            a = getattr(self,name,None)
            if a is not None: f = L(a)+f
            setattr(self, name, f)

    def setup(self, items=None, train_setup=False):
        print("In Pipeline: in setup")
        tfms = self.fs[:]
        print("In Pipeline: in setup: tfms ", [t.name for t in tfms])
        self.fs.clear()
        for t in tfms: self.add(t,items, train_setup)

    def add(self,t, items=None, train_setup=False):
        print("In Pipeline: in add")
        print("In Pipeline: t type: ", type(t), " t ", t.name)
        t.setup(items, train_setup)
        print("In Pipeline: returned from setup")
        self.fs.append(t)

    

        

    def __call__(self, o): return compose_tfms(o, tfms=self.fs, split_idx=self.split_idx)
    def __repr__(self): return f"Pipeline: {' -> '.join([f.name for f in self.fs if f.name != 'noop'])}"
    def __getitem__(self,i): return self.fs[i]
    def __setstate__(self,data): self.__dict__.update(data)
    def __getattr__(self,k): return gather_attrs(self, k, 'fs')
    def __dir__(self): return super().__dir__() + gather_attr_names(self, 'fs')

    def decode  (self, o, full=True):
        if full: return compose_tfms(o, tfms=self.fs, is_enc=False, reverse=True, split_idx=self.split_idx)
        #Not full means we decode up to the point the item knows how to show itself.
        for f in reversed(self.fs):
            if self._is_showable(o): return o
            o = f.decode(o, split_idx=self.split_idx)
        return o

    def show(self, o, ctx=None, **kwargs):
        o = self.decode(o, full=False)
        o1 = (o,) if not _is_tuple(o) else o
        if hasattr(o, 'show'): ctx = o.show(ctx=ctx, **kwargs)
        else:
            for o_ in o1:
                if hasattr(o_, 'show'): ctx = o_.show(ctx=ctx, **kwargs)
        return ctx

    def _is_showable(self, o):
        if hasattr(o, 'show'): return True
        if _is_tuple(o): return all(hasattr(o_, 'show') for o_ in o)
        return False