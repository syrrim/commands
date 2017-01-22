commands.py
===========

This is a module for transforming python functions into shell commands. The goal
is to make pythonic commands that can be run using familiar command line
conventions. It operates by interpreting the signature of a python function, and
using it to transform command-line arguments into arguments to a function. For
example:

    def sum(*args:int):
        base = 0
        for a in args:
            base += a
        return base

    if __name__ == "__main__":
        import commands
        commands.main(sum)

    >>>python3 sum.py 1 2 3 4
    10

Configuration is performed by altering the signature. To take an argument as a
flag, make it a keyword argument:
    
    def count(*args, verbose=False):
        c = 0
        for a in args:
            c += 1
            if verbose:
                print("{c}!")
        return c


    >>>python3 count.py a b c d --verbose
    1!
    2!
    3!
    4!
    4

To gain greater control, create an instance of `commands.Arg`, and pass it as an
annotation:
    
    class Coord(commands.Arg):
        @commands.coercer
        def pos(self):
            return lambda x: (float(next(x)), float(next(x)))

    def area(top:Coord(short), bot:Coord()):
        return (bot[0] - top[0]) * (bot[1] - top[1])
    

    >>>python3 area.py 0 0 10 10
    100

Short flags can be specified as well. Because they have no parallel in python,
they can become quite verbose.  

Booleans can be switched between using `BoolEnum`. First create an enum mapping a
long string to a single character one. (this can be done with commands.flags).
Then pass the "truthy" instance of your enum to `BoolEnum`:

    def rm(recursive: BoolEnum( flags(("rec","r"),("not_rec","R")).rec ) = False):
        if recursive:
            return rm(recursive)
        return "Done"

    >>>python3 rm.py -r
    RecursionError: maximum recursion depth exceeded
    >>>python3 rm.py
    Done
    >>>

Multiple flags can be switched between with the flags function:

    modes = flags(("extract", "x"), ("create", "c"), ("diff", "d"))
    def tar(mode:EnumArg(modes), file:Arg(short="f")):
        if mode == modes.create:
            ...

    >>>python3 tar.py -xf "file.tar"

TODO
----

 - Ability to generate help strings

 - More concise ways of doing common operations
