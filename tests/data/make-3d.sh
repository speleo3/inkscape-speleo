#!/bin/sh
for enc in latin1 utf8; do
    for v in 3 4 5 6 7 8; do
        out="3d/umlaut-$enc-v$v.3d"
        if [[ ! -f "$out" ]]; then
            cavern -v $v -o "$out" umlaut-$enc.svx
        fi
    done
done
