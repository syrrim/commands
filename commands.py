from inspect import signature, Parameter
import enum
import sys
import itertools
import functools
import traceback
import readline

def parse_args(args, positional, var_pos, long_flags, short_flags, var_kw, consume=True):
    pos_args = []
    options = {}
    iter_args = iter(args) # may already be an iterator
    more_kw = True # '--' signals the end of keyword arguments
    for arg in iter_args:
        if more_kw and isinstance(arg, str):
            if arg in long_flags:
                f = long_flags[arg]
                options[f.name] = f(iter_args)
                continue

            if arg == "--":
                more_kw = False
                continue

            if var_kw is not None and arg.startswith("--"):
                name = arg[2:].replace("-", "_")
                options[name] = var_kw(iter_args)
                continue

            if arg[0] == "-" and len(arg) > 1 and all(c in short_flags for c in arg[1:]):
                for c in arg[1:]:
                    f = short_flags[c]
                    options[f.name] = f(iter_args)
                continue

        if len(positional) > len(pos_args):
            pos_args.append(positional[len(pos_args)](itertools.chain([arg], iter_args)))
            continue

        if var_pos is not None:
            pos_args.append(var_pos(itertools.chain([arg], iter_args)))
            continue 

        if consume:
            print(positional, args)
            raise TypeError("Too many arguments: needed {}, {} given".format(len(positional), len(args)))
        return pos_args, options, itertools.chain([arg], iter_args)

    return pos_args, options, iter(())

class Coercer:
    def __init__(self, name, f):
        self.name = name
        self.f = f

    def __call__(self, x):
        return self.f(x)

def coercer(b_f):
    @functools.wraps(b_f)
    def w(self, *args):
        return Coercer(self.name, b_f(self, *args))
    return w

class Arg:
    def __init__(self, short=None):
        self.name = None
        self.short_str = short

    def baptize(self, name):
        self.name = name

    @coercer
    def pos(self):
        return lambda x: next(x)

    def var(self):
        return self.pos()

    def long(self, di):
        di["--"+self.name.replace("_", "-")] = self.pos()

    def short(self, di):
        if self.short is not None:
            di[self.short_str] = self.pos()

    def kw(self):
        return self.pos()

class TypeArg(Arg):
    def __init__(self, type, short=None):
        self.type = type
        Arg.__init__(self, short)

    @coercer
    def pos(self):
        return lambda x: self.type(next(x))

class EnumArg(Arg):
    def __init__(self, type):
        self.type = type

    def member(self, val):
        return self.type[val]

    @coercer
    def pos(self):
        return lambda x: self.member(next(x))

    def short(self, di):
        # expects members to point to singles chars. 
        for member in self.type:
            di[member.value] = Coercer(self.name, lambda x, name=member.name: self.member(name))

def flags(*pairs):
    names, shorts = zip(*pairs)
    return enum.Enum("Enum_"+"_".join(names), pairs)

class BoolEnum(EnumArg):
    def __init__(self, true):
        self.true = true
        EnumArg.__init__(self, type(self.true))

    def member(self, val):
        return self.type[val] == self.true


class BoolArg(Arg):
    @coercer
    def pos(self):
        return lambda x: next(x)[0].lower() in "yt"#yes/true

    def long(self, di):
        di["--" + self.name.replace("_", "-")] = Coercer(self.name, lambda x: True)
        di["--no-" + self.name.replace("_", "-")] = Coercer(self.name, lambda x: False)


def get_arg(param):
    if isinstance(param.annotation, Arg):
        return param.annotation
    if param.annotation is not Parameter.empty and isinstance(param.annotation, type):
        return TypeArg(param.annotation)
    if isinstance(param.default, enum.Enum):
        return EnumArg(type(param.default))
    if isinstance(param.default, bool):
        return BoolArg(param.name)
    if param.default is not None and param.default is not Parameter.empty:
        return TypeArg(type(param.default))
    return Arg()
           

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
            p = params[param]
            arg = get_arg(p)
            arg.baptize(p.name)
            #POSITIONAL_OR_KEYWORD is the default for regular python args
            if p.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD):
                pos.append(arg.pos())
            if p.kind == Parameter.VAR_POSITIONAL:
                var_pos = arg.var()
            if p.kind in (Parameter.KEYWORD_ONLY, Parameter.POSITIONAL_OR_KEYWORD):
                arg.long(long_flags)
                arg.short(short_flags)
            if p.kind == Parameter.VAR_KEYWORD:
                var_kw = arg.kw()

        usage = "{name}"
        def new_func(self, *args):
            pos_args, options, _ = parse_args(args, *self.args)
            print(pos_args, options)
            return func(*pos_args, **options)
            
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
                #if attr_name == "__init__":
                #    for pos in functions[attr_name].args[0]:
                #        if pos.default != Parameter.empty:
                #            raise Exception("Init method shouldn't have optional positional args")
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

