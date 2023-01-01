#! /usr/bin/python3

import atheris
import sys

with atheris.instrument_imports():
    import msgspec
    from typing import Optional, Set


@atheris.instrument_func
def test_input(input_bytes):
    fdp = atheris.FuzzedDataProvider(input_bytes)
    input_string = fdp.ConsumeUnicodeNoSurrogates(sys.maxsize)
    input_str_w_surrogates = fdp.ConsumeUnicode(sys.maxsize)
    input_int = fdp.ConsumeInt(sys.maxsize)
    
    try:
        class User(msgspec.Struct):
            name: str
            # groups: Set[str] = set()
            # email: Optional[str] = None

        alice = User(input_string, groups={input_string, input_string})
        # msg = msgspec.json.encode(alice)
        # msgspec.json.decode(msg, type=User)
    except msgspec.ValidationError:
        pass
    except TypeError:
        pass

def main():
    atheris.Setup(sys.argv, test_input)
    atheris.Fuzz()

if __name__ == "__main__":
    main()
