## Sorts chunks into languages
## First run put_chunks_here/splitter.sh

import numpy as np
import os
import json
import unicodedata

splits = np.array([f for f in os.listdir("put_chunks_here") if f[0]=="x"])

langlist = {}
exceptions = []


def create_directory_name(langname):
    """
    Creates ASCII directory name for a language name.
    """
    langname = langname.replace(" ", "_")
    normalized_text = unicodedata.normalize('NFKD', langname)
    #return ''.join([c for c in normalized_text if unicodedata.category(c) != 'Mn' and c not in "!' ()"])
    return ''.join([c for c in normalized_text if c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"])
    
for split in splits:
    with open("put_chunks_here/" + split, 'r') as f:
        lines = [l for l in f.read().split('\n') if len(l) > 0]
    for line in lines:
        dat = json.loads(line)
        if "lang" not in dat.keys():
            if "pos" in dat.keys() and dat['pos'] == 'hard-redirect':
                "a redirect page -- ignore"
            else:
                exceptions.append(dat)
        else:
            dat_lang = dat["lang"]
            if dat_lang not in langlist.keys():
                print((dat_lang, create_directory_name(dat_lang)))
                langlist[dat_lang] = []
            langlist[dat_lang].append(line)

# for k, v in langlist.items():
#     print((k, len(v)), end=" ")
# print()


#"  ".join([create_directory_name(k) for k in langlist.keys()])

lang2dir = {k: create_directory_name(k) for k in langlist.keys()}

os.makedirs("languages", exist_ok=True)

for k, v in langlist.items():
    os.makedirs("languages/%s" % lang2dir[k], exist_ok=True)
    with open("languages/%s/wiktextract-data.jsonl" % lang2dir[k], 'w') as f:
        f.write("\n".join(v))

