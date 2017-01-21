from commands import command, Option as opt

def test_basic():
    @command
    def add(first:int, second:int):
        return first + second

    assert add("1", "2") == 3

def test_var_kw():
    @command
    def switch(*values:str, indent=False, cr=False):
        return ("\n" + ("\r" if cr else "") + ("    " if indent else "")).join(values)
        
    assert switch("1", "2", "--indent", "3", "4") == "1\n    2\n    3\n    4"

def test_class():
    @command
    class Main:
        def __init__(self, pos_arg:int, *, clement=False):  
            self.val = pos_arg
            self.clement = clement

        def value(self):    
            return self.val

        def carry(self, val:int):
            if self.clement:
                return self.val + val
            else:
                return val

    assert Main("17", "--clement", "value") == 17
    assert Main("6", "carry", "6") == 6

def test_kw():
    @command
    def tries(*args:float, **kwargs:int):
        return args, kwargs

    assert tries("--grape", "7", "--pear", "22", "14.4") == ((14.4,), {"grape": 7, "pear": 22})
