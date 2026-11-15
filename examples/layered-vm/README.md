# Example: layered VM constant recovery

Real output from one run of the `layered` engine on a 1.28 MB single-line Luau
VM protector (multi-layer alias header, base-87 constant pool, stream-cipher
strings, Zstd-packed payload).

```console
$ python deob_live.py target.lua --stubs
file      : target.lua
functions : 164 defined, 119 calls recorded
values    : 24
strings   : 15 unique plaintext
blobs     : 2 binary payloads
stopped   : stack overflow          # the protector's own anti-tamper path
output    : out_live/target
```

Files in this folder are exactly what the engine wrote:

| file | what it shows |
|---|---|
| `strings.txt` | `call<TAB>plaintext` for every decrypted string |
| `recovered_strings.lua` | the same data as a Lua table |
| `blobs.json` | the binary payloads it produced, with sizes, ASCII ratio and a bytecode flag |
| `report.json` | instrumentation counts and where the replay stopped |

The strings tell you what the protected script actually touches: service names,
engine class names, the VM's internal builtin table. That is usually the first
question anyone has about an unknown protected script.
