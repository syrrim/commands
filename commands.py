from inspect import signature, Parameter
import sys
import itertools
import traceback
import readline


class Option:
    def __init__(self, type: type=None, short: str=None, doc: str=None, typename: str=None):
        self.type = type
        self.short = short
        self.doc = doc
        self.typename = typename

    @classmethod
    def from_props(cls, default, anno):
        if isinstance(anno, cls):
            inst = anno
        else:
            inst = cls()

        if inst.type is None 
            if isinstance(anno, type):
                inst.type = anno
            elif inst.type is None and inst.default not in (Parameter.empty, None):
                inst.type = type(default)

        if inst.typename is None 
            if inst.type is not None:
                inst.typename = inst.type.__name__.upper()
            else:
                inst.typename = "VAL"

        return inst
            

    def argument(self, name):

class BoolOption(Option):
    def __init__(self, short=None, doc=None):
        self.short = short
        self.doc = doc

    def argument(self, name):


    


class Argument:
    def __init__(self, name, coerce):
        self.name = name
        self.coerce = coerce

    @classmethod
    def static(cls, val):
        return lambda it: val

    @classmethod
    def first(cls, it):
        return next(it)

    @classmethod
    def call(cls, f):
        def w(it):
            try:
                val = next(it)
                return f(val)
            except:
                return val
        return w
    
    @classmethod
    def type_coerce(cls, type_):
        if type_ == bool:
            return cls.static(True)
        elif type_ == list:
            return cls.call(lambda s: s.split(","))
        return cls.call(type_) # works for str, int, float, etc.
        
    @classmethod
    def get_type(cls, param):
        ano = param.annotation
        if isinstance(ano, Option):
           if ano.type:
                return ano.type
        elif isinstance(ano, type):
            return ano
        elif param.default is not Parameter.empty and param.default is not None:
            return type(param.default)

        
    @classmethod
    def create(cls, param):
        return cls(param.name, cls.get_coerce(param))
        
    @classmethod
    def bool_pairs(cls, param):
        return cls(param.name, cls.static(True)), cls(param.name, cls.static(False))
    

class Blank:
    def __init__(self, name, default, kind, annotation):
        self.name = name
        self.default = default
        self.list = True if kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD) else False
        self.kind = kind

        self.type = None
        self.doc = None
        self.short = None
        self.typename = None

        if annotation is not Parameter.empty:
            if isinstance(annotation, Option):
                self.type = annotation.type
                self.doc = annotation.doc
                self.short = annotation.short
                self.typename = annotation.typename
            elif hasattr(annotation, "__call__"): #could be type, but all it needs is to be able to coerce
                self.type = annotation
            elif isinstance(annotation, str):
                self.doc = annotation
        if self.type is None and self.default != Parameter.empty and self.default is not None:
            self.type = type(self.default)
        if self.typename is None and self.type is not None:
            self.typename = self.type.__name__.upper()
            

    def coerce(self, string):
        try:
            return self.type(string)
        except Exception: #type might not exist, might not accept strings. 
            return string

    def coerce_iter(self, it):
        if self.type == bool:
            return True
        return self.coerce(next(it))

    def doc(self):
        result = ""
        if self.default is not Parameter.empty:
            result += "--"
        result += self.name
        if self.short is not None:
            result += ", -" + self.short
        if self.doc:
            result += ": " + self.doc
        elif self.type:
            result += ": " + str(self.type)
        return result

    def inline(self):
        result = ""
        if self.short:
            result += "-" + self.short
        else:
            result += "--" + self.name 
        if self.type != bool:
            result += " "
            if self.typename is not None:
                result += self.typename
            else:
                result += "VAL"
        if self.default != Parameter.empty:
            return "[" + result + "]"
        return result

    def __str__(self):
        return self.name + ":" + str(self.type) + "=" + str(self.default)

    def __repr__(self):
        return "{}('{}', {}, Option(type={}, short={}, doc={}))".format(
                self.__class__.__name__, self.name, self.default, 
                                    self.type, self.short, self.doc)


def parse_args(args, positional, var_pos, long_flags, short_flags, var_kw, consume=True):
    pos_args = []
    options = {}
    iter_args = iter(args) # may already be an iterator
    more_kw = True # '--' signals the end of keyword arguments
    for arg in iter_args:
        if more_kw and isinstance(arg, str):
            if arg in long_flags:
                f = long_flags[arg]
                options[f.name] = f.coerce(iter_args)
                continue

            if arg == "--":
                more_kw = False
                continue

            if var_kw is not None and arg.startswith("--"):
                name = arg[2:].replace("-", "_")
                options[name] = var_kw.coerce(iter_args)
                continue

            if arg[0] == "-" and len(arg) > 1 and all(c in short_flags for c in arg[1:]):
                for c in arg[1:]:
                    f = short_flags[c]
                    options[f.name] = f.coerce(iter_args)
                continue

        if len(positional) > len(pos_args):
            pos_args.append(positional[len(pos_args)].coerce([arg]))
            continue

        if var_pos is not None:
            pos_args.append(var_pos.coerce([arg]))
            continue 

        if consume:
            print(positional, args)
            raise TypeError("Too many arguments: needed {}, {} given".format(len(positional), len(args)))
        return pos_args, options, itertools.chain([arg], iter_args)

    return pos_args, options, ()


class Command:
    def __init__(self, func, doc, args):
        self.func = func
        self.doc = doc
        self.args = args

    def __call__(self, *args):
        return self.func(self, *args)

    @classmethod
    def create_function(cls, func):
        pos = []
        long_flags = {}
        short_flags = {}
        keyword = []
        var_pos = None
        var_kw = None

        params = signature(func).parameters
        for param in params:
            type_ = Argument.get_type(param)
            arg = Argument.create(param)
            #POSITIONAL_OR_KEYWORD is the default for regular python args
            if arg.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD):
                pos.append(arg)
            if arg.kind == Parameter.VAR_POSITIONAL:
                var_pos = arg
            if arg.kind in (Parameter.KEYWORD_ONLY, Parameter.POSITIONAL_OR_KEYWORD):
                long_flags["--" + arg.name.replace("_", "-")] = arg
                if arg.type == bool:
                    long_flags["--no-" + arg.name.replace("_", "-")] = arg.invert()
                    
                if arg.short is not None:
                    short_flags[arg.short] = arg
            if arg.kind == Parameter.KEYWORD_ONLY:
                keyword.append(arg)
            if arg.kind == Parameter.VAR_KEYWORD:
                var_kw = arg

        usage = "{name}"
        for p in pos[0 if hasattr(func, "im_self") else 1:]: #if bound function, skip `self` arg
            if p.default is not Parameter.empty:
                usage += " [" + p.name.upper() + "]"
            else:
                usage += " " + p.name.upper()
        if var_pos is not None:
            usage += " [ " + var_pos.name.upper() + " ...]"
        for kw in keyword:
            usage += " " + kw.inline()
        if var_kw is not None:
            usage += " [" + var_kw.inline() + " ...]"
        if func.__doc__ != None:
            usage += "\n" + func.__doc__ 

        def new_func(self, *args):
            pos_args, options, length = parse_args(args, *self.args)
            return func(*pos_args, **options)
            `
        return cls(new_func, usage, (pos, var_pos, long_flags, short_flags, var_kw))

    @staticmethod
    def format_doc(functions, class_):
        usage = ""
        if "__init__" in functions:
            usage += functions["__init__"].doc # starts with "{name}"
        not_init = [i for i in functions if i != "__init__"]
        usage += " " + "|".join(not_init)
        if class_.__doc__ is not None:
            usage += "\n" + class_.__doc__
        for name in not_init:
            usage += "\n\n    " + functions[name].doc.format(name=name).replace("\n", "\n    ")
        return usage

    @staticmethod
    def choose_kind(inst, class_, kind):
        if kind == "static":
            return []
        elif kind == "class":
            return [class_]
        elif kind == "instance":
            return [inst]

    @classmethod
    def create_class(cls, class_):
        functions = {}
        for attr_name in class_.__dict__:
            if attr_name != "__init__" and attr_name[:2] == "__":
                continue
            attr = getattr(class_, attr_name)
            if isinstance(attr, type):
                functions[attr_name] = cls.create_class(attr)
                functions[attr_name].kind = "static"
            elif hasattr(attr, "__call__"):
                functions[attr_name] = cls.create_function(attr)
                kind = "instance"
                if isinstance(class_.__dict__[attr_name], classmethod):
                    kind = "class"
                if isinstance(class_.__dict__[attr_name], staticmethod):
                    kind = "static"
                functions[attr_name].kind = kind
                if attr_name == "__init__":
                    for pos in functions[attr_name].args[0]:
                        if pos.default != Parameter.empty:
                            raise Exception("Init method shouldn't have optional positional args")
        def call(self, *args):
            args = iter(args)
            if "__init__" in functions:
                init = functions["__init__"]
                init_args, init_kw, args = parse_args(args, init.args[0][1:], #skip parsing self
                                                *init.args[1:], consume=False)
                print(init_args, init_kw)
                inst = class_(*init_args, **init_kw)
            else:
                inst = class_()

            try:
                command_name = next(args) # might be empty
                if command_name in functions:
                    cmd = functions[command_name]
                    return cmd(*cls.choose_kind(inst, class_, cmd.kind), *args)
                else:
                    raise Exception("unrecognized command: '{}'".format(command_name))

            except StopIteration: #time to go interactive
                readline.parse_and_bind("") #TODO: tab completion bullshit
                while True:
                    try:
                        line = input().strip() # automagically readline enabled
                    except EOFError:
                        break
                    if not line:
                        continue
                    args = line.split() #around spaces
                    command_name = args.pop(0)
                    if command_name in functions:
                        cmd = functions[command_name]
                        cmd(*cls.choose_kind(inst, class_, cmd.kind), *args)
                    else:
                        print("unrecognized command: '{}'".format(command_name), file=sys.stderr)

        return cls(call, Command.format_doc(functions, class_), None)


def command(func_or_class):
    if isinstance(func_or_class, type):
        return Command.create_class(func_or_class)
    elif hasattr(func_or_class, "__call__"):
        return Command.create_function(func_or_class)
    else:
        raise TypeError("first arg must be function or class")


def main(func_or_class):
    cmd = command(func_or_class)
    try:
        result = cmd(*sys.argv[1:])
    except Exception as e:
        traceback.print_exc() # to be removed
        print(e, file=sys.stderr)
        print(cmd.doc.format(name=sys.argv[0]), file=sys.stderr)
        exit(1)
    else:
        if hasattr(result, "__next__"):
            for line in result:
                if line is None:
                    continue
                print(line)
        elif result is not None:
            print(result)

