# typing.py - Dummy module to prevent ImportErrors
def Any(x): return x
def Union(*args): return args
def Tuple(*args): return args
def List(*args): return args
def Optional(x): return x
def Callable(*args): return args
def TypeVar(name, *args, **kwargs): return name
